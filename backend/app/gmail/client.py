"""Gmail API connection (OAuth 2.0, Desktop client).

Where the token comes from:
  laptop  GMAIL_TOKEN_FILE  - written once by `python -m scripts.gmail_auth`
  Azure   GMAIL_TOKEN_JSON  - the same JSON, injected from Key Vault secret "gmail-token"

The token holds a long-lived refresh token; short-lived access tokens are renewed
automatically. Token contents are never logged or printed.
"""
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",  # read, label, import into the inbox
    "https://www.googleapis.com/auth/gmail.send",    # outbound e-mails (M09, always redirected)
]


class GmailNotConfigured(RuntimeError):
    pass


def load_credentials() -> Credentials:
    s = get_settings()
    if s.gmail_token_json:
        creds = Credentials.from_authorized_user_info(json.loads(s.gmail_token_json), SCOPES)
        token_path = None
    elif s.gmail_token_file and Path(s.gmail_token_file).exists():
        token_path = Path(s.gmail_token_file)
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    else:
        raise GmailNotConfigured(
            "No Gmail token. On the laptop run `python -m scripts.gmail_auth` (needs GMAIL_CLIENT_SECRET_FILE "
            "and GMAIL_TOKEN_FILE in .env); in Azure store the token in Key Vault secret 'gmail-token'."
        )
    if not creds.valid:
        if not creds.refresh_token:
            raise GmailNotConfigured("Gmail token has no refresh token - run `python -m scripts.gmail_auth` again.")
        creds.refresh(Request())
        if token_path:  # keep the laptop file current (Azure keeps using the refresh token)
            token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service(creds: Credentials | None = None):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds or load_credentials(), cache_discovery=False)


_label_ids: dict[str, str] = {}  # label name -> Gmail label id (per process)


def ensure_label(service, name: str) -> str:
    """Id of the Gmail label `name`, creating it if needed."""
    if name in _label_ids:
        return _label_ids[name]
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for lab in labels:
        if lab["name"].lower() == name.lower():
            _label_ids[name] = lab["id"]
            return lab["id"]
    created = service.users().labels().create(
        userId="me", body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    ).execute()
    _label_ids[name] = created["id"]
    return created["id"]


def run_consent_flow(client_secret_file: str, token_file: str) -> str:
    """One-time browser consent on the laptop. Writes the token file; returns the Gmail address."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline",
                                  authorization_prompt_message="Opening the browser for Google sign-in...")
    Path(token_file).parent.mkdir(parents=True, exist_ok=True)
    Path(token_file).write_text(creds.to_json(), encoding="utf-8")
    profile = build_service(creds).users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "")
