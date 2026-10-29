"""Check a running API end to end with the demo login (counts and timings only - no data is printed).

Run from the backend folder:
    python -m scripts.check_api <api base url> [user e-mail]

It asks for the demo access code (typing is hidden). The code is only sent to the login call.
"""
import getpass
import json
import sys
import time
import urllib.error
import urllib.request


def call(base: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(base.rstrip("/") + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, status, headers = r.read(), r.status, r.headers
    except urllib.error.HTTPError as exc:
        raw, status, headers = exc.read(), exc.code, exc.headers
    return status, raw, headers, time.perf_counter() - started


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    base, user = argv[0], (argv[1] if len(argv) > 1 else "analyst@acme-demo.local")
    code = getpass.getpass("Demo access code: ")
    s, raw, _, t = call(base, "/api/auth/demo-login", body={"user": user, "access_code": code})
    del code
    print(f"login: {s} ({t:.1f}s)")
    if s != 200:
        return 1
    token = json.loads(raw)["token"]
    ok = True

    def check(name: str, path: str, show):
        nonlocal ok
        s, raw, _, t = call(base, path, token)
        good = s == 200
        ok &= good
        print(f"{name}: {s} ({t:.2f}s)" + (f" - {show(json.loads(raw))}" if good else ""))
        return json.loads(raw) if good else None

    lst = check("work-items", "/api/work-items?page_size=20", lambda d: f"{d['total']} rows, first page {len(d['items'])}")
    check("work-items filtered", "/api/work-items?status=PENDING_REVIEW&sort=confidence&order=asc&page_size=5",
          lambda d: f"{d['total']} pending review")
    if lst and lst["items"]:
        row = next((i for i in lst["items"] if i["decision"] != "OUT_OF_SCOPE"), lst["items"][0])
        d = check("detail", f"/api/work-items/{row['id']}", lambda d: f"{len(d['attachments'])} attachment(s), "
                  f"{len(d['candidates'])} candidate(s), {len(d['audit'])} audit entries, actions {len(d['allowed_actions'])}")
        if d and d["attachments"]:
            s, raw, h, t = call(base, d["attachments"][0]["url"])  # signed link, no token
            print(f"signed file link (no header): {s}, {h.get('Content-Type')}, {len(raw)} bytes")
            ok &= s == 200
    check("kpis", "/api/kpis", lambda d: f"total {d['cards']['total']['count']}, ai {d['cards']['ai']['count']}, "
          f"manual {d['cards']['manual']['count']}, dup {d['cards']['duplicates']['count']}, "
          f"exc {d['cards']['exceptions']['count']}, USD unconverted {d['usd']['unconverted']}")
    check("audit", "/api/audit?page_size=5", lambda d: f"{d['total']} entries")
    check("changes", "/api/changes?since=2026-01-01T00:00:00Z", lambda d: f"{d['new_work_items']['count']} new rows")
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
