"""File storage for raw e-mails and attachments.

Two backends, chosen by STORAGE_BACKEND:
  local       files under STORAGE_LOCAL_ROOT (laptop)           uri  local:emails/EML-000001/message.eml
  azure_blob  Azure Blob container, signed in with the managed  uri  blob:emails/EML-000001/message.eml
              identity (no account keys)

The rest of the app only sees `put()` / `get()` and the returned URI, so it never
needs to know where a file really lives.
"""
import hashlib
import re
import unicodedata
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.config import get_settings


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(name: str, default: str = "file") -> str:
    """A file name that is safe on Windows, Linux and in blob paths (keeps the extension)."""
    name = unicodedata.normalize("NFKC", name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:150] or default


def _clean_path(path: str) -> str:
    """Relative POSIX path without '..' or leading slashes."""
    parts = [p for p in PurePosixPath(path.replace("\\", "/")).parts if p not in ("", ".", "..", "/")]
    if not parts:
        raise ValueError(f"empty storage path: {path!r}")
    return "/".join(parts)


class Storage(Protocol):
    def put(self, path: str, data: bytes, content_type: str | None = None) -> str: ...
    def get(self, uri: str) -> bytes: ...


class LocalStorage:
    scheme = "local"

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put(self, path: str, data: bytes, content_type: str | None = None) -> str:
        rel = _clean_path(path)
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"{self.scheme}:{rel}"

    def get(self, uri: str) -> bytes:
        return (self.root / _clean_path(_strip_scheme(uri, self.scheme))).read_bytes()


class AzureBlobStorage:
    scheme = "blob"

    def __init__(self, account_url: str, container: str, client_id: str = ""):
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        credential = DefaultAzureCredential(managed_identity_client_id=client_id or None)
        self.container = BlobServiceClient(account_url, credential=credential).get_container_client(container)

    def put(self, path: str, data: bytes, content_type: str | None = None) -> str:
        from azure.storage.blob import ContentSettings

        rel = _clean_path(path)
        self.container.upload_blob(rel, data, overwrite=True,
                                   content_settings=ContentSettings(content_type=content_type) if content_type else None)
        return f"{self.scheme}:{rel}"

    def get(self, uri: str) -> bytes:
        return self.container.download_blob(_clean_path(_strip_scheme(uri, self.scheme))).readall()


def _strip_scheme(uri: str, scheme: str) -> str:
    prefix = f"{scheme}:"
    if not uri.startswith(prefix):
        raise ValueError(f"{uri!r} is not a {scheme} storage uri")
    return uri[len(prefix):]


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "azure_blob":
        if not s.azure_storage_account_url:
            raise RuntimeError("STORAGE_BACKEND=azure_blob needs AZURE_STORAGE_ACCOUNT_URL")
        return AzureBlobStorage(s.azure_storage_account_url, s.azure_storage_container, s.azure_client_id)
    return LocalStorage(s.storage_local_root)
