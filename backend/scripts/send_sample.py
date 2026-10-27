"""Put sample e-mails into the Gmail inbox with the customer as sender.

Run from the backend folder:
    python -m scripts.send_sample R01-0007
    python -m scripts.send_sample R01-0007 R30-0165
    python -m scripts.send_sample --all-live        # the held-back live set (chosen in M11)
"""
import sys

from app.gmail.client import build_service
from app.gmail.sample_sender import live_set, send_sample


def main(argv: list[str]) -> int:
    codes = [a for a in argv if not a.startswith("--")]
    if "--all-live" in argv:
        try:
            codes += live_set()
        except FileNotFoundError as exc:
            print(exc)
            return 1
    if not codes:
        print(__doc__)
        return 1
    service = build_service()
    failed = 0
    for code in codes:
        try:
            r = send_sample(service, code)
            print(f"{code}: in inbox (gmail id {r['gmail_id']}) from {r['from']} - "
                  f"'{r['subject']}' - attachments: {', '.join(r['attachments']) or 'none'}")
        except Exception as exc:
            failed += 1
            print(f"{code}: FAILED - {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
