"""The sample e-mails (data/samples/emails/<CODE>/ + data/samples/live_set.txt), wherever they are kept.

  laptop / tests   the folder data/samples (SAMPLES_ROOT = .../emails)
  Azure            the Blob container, under the prefix "samples/" (same layout; uploaded once from the laptop).
                   The images do not contain the samples (42 MB).

`load(code)` returns a `Sample` whose attachments can be read with `.name` / `.read_bytes()` (like Paths), so
`sample_sender.build_message` works with either source.
"""
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.gmail.sample_sender import Sample, load_sample, samples_root
from app.storage import Storage, get_storage

BLOB_PREFIX = "samples"
HEADER_KEYS = ("from", "subject", "date", "to", "cc")


@dataclass
class SampleFile:
    name: str
    data: bytes

    def read_bytes(self) -> bytes:
        return self.data


def _number(code: str) -> int:
    return int(code.split("-")[1])


def parse_body(code: str, text: str, files: list[SampleFile]) -> Sample:
    text = text.lstrip("﻿").replace("\r\n", "\n")
    head, _, body = text.partition("\n\n")
    headers: dict[str, str] = {}
    for line in head.split("\n"):
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() in HEADER_KEYS:
            headers[key.strip().lower()] = value.strip()
    return Sample(code, headers, body.strip("\n") + "\n", files)  # type: ignore[arg-type]


class LocalLibrary:
    def __init__(self, root: Path):
        self.root = root

    def codes(self) -> list[str]:
        return sorted((p.name for p in self.root.iterdir() if p.is_dir() and (p / "body.txt").exists()), key=lambda c: (c.split("-")[0], _number(c)))

    def load(self, code: str) -> Sample:
        return load_sample(code, self.root)

    def live_set_text(self) -> str | None:
        f = self.root.parent / "live_set.txt"
        return f.read_text(encoding="utf-8") if f.exists() else None


class StorageLibrary:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.base = f"{BLOB_PREFIX}/emails"

    def codes(self) -> list[str]:
        found = {p[len(self.base) + 1:].split("/")[0] for p in self.storage.list(self.base) if p.endswith("/body.txt")}
        return sorted(found, key=lambda c: (c.split("-")[0], _number(c)))

    def load(self, code: str) -> Sample:
        prefix = f"{self.base}/{code}"
        paths = [p for p in self.storage.list(prefix) if p != f"{prefix}/body.txt"]
        try:
            body = self.storage.get(f"{self.storage.scheme}:{prefix}/body.txt").decode("utf-8")
        except Exception as exc:  # missing blob
            raise FileNotFoundError(f"Sample {code} not found in storage ({prefix}/body.txt)") from exc
        files = [SampleFile(p.rsplit("/", 1)[-1], self.storage.get(f"{self.storage.scheme}:{p}")) for p in paths]
        return parse_body(code, body, files)

    def live_set_text(self) -> str | None:
        try:
            return self.storage.get(f"{self.storage.scheme}:{BLOB_PREFIX}/live_set.txt").decode("utf-8")
        except Exception:
            return None


def get_library() -> LocalLibrary | StorageLibrary:
    """The local folder when it exists (laptop, tests), else the storage container (Azure)."""
    root = samples_root()
    if root.exists():
        return LocalLibrary(root)
    s = get_settings()
    if s.storage_backend != "azure_blob":
        return LocalLibrary(root)  # nothing there: callers get a clear "not found"
    return StorageLibrary(get_storage())


def live_set(library=None) -> list[str]:
    text = (library or get_library()).live_set_text()
    if text is None:
        raise FileNotFoundError("No live set found (data/samples/live_set.txt, or samples/live_set.txt in the storage container).")
    return [c.strip() for c in text.splitlines() if c.strip() and not c.startswith("#")]


def history_set(library=None) -> list[str]:
    """Every sample that is not in the live set, oldest sample number first (promises come before their payments)."""
    lib = library or get_library()
    live = set(live_set(lib))
    return sorted((c for c in lib.codes() if c not in live), key=lambda c: (_number(c), c))
