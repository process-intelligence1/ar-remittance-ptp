"""One-time Gmail sign-in on the laptop.

Run from the backend folder:
    python -m scripts.gmail_auth

Opens the browser, you sign in as processintelligence1@gmail.com and allow access.
The token is written to GMAIL_TOKEN_FILE (outside the repo). Nothing secret is printed.
"""
import sys
from pathlib import Path

from app.config import PROJECT_ROOT, get_settings
from app.gmail.client import run_consent_flow


def main() -> int:
    s = get_settings()
    if not s.gmail_client_secret_file or not Path(s.gmail_client_secret_file).exists():
        print("GMAIL_CLIENT_SECRET_FILE in .env is missing or the file does not exist.")
        return 1
    if not s.gmail_token_file:
        print("GMAIL_TOKEN_FILE is not set in .env.")
        return 1
    if Path(s.gmail_token_file).resolve().is_relative_to(PROJECT_ROOT.resolve()):
        print("GMAIL_TOKEN_FILE must be OUTSIDE the project folder (e.g. D:\\Finance\\Secret\\gmail_token.json).")
        return 1
    address = run_consent_flow(s.gmail_client_secret_file, s.gmail_token_file)
    print(f"Signed in as {address}. Token saved to GMAIL_TOKEN_FILE.")
    if address.lower() != s.gmail_address.lower():
        print(f"WARNING: expected {s.gmail_address} - run again and pick that account.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
