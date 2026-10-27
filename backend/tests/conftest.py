"""Shared test fixtures.

- db:          a session on the laptop database inside a transaction that is rolled back at the
               end of each test (commits in the code under test become savepoints), so tests never
               leave data behind.
- storage:     LocalStorage in a temporary folder.
- fake_gmail:  an in-memory stand-in for the Gmail API (no network, no real mailbox).
"""
import base64
import itertools

import pytest
from sqlalchemy.orm import Session

from app.db import engine
from app.storage import LocalStorage


@pytest.fixture
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def poller_on(monkeypatch):
    """Tests poll a FAKE mailbox, so the POLLER_ENABLED guard is switched on for them.
    Tests of the guard itself switch it off again."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "poller_enabled", True)


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "files")


# --------------------------------------------------------------------------- fake Gmail API
class _Call:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class FakeGmail:
    """Implements the handful of Gmail calls the app uses. Messages live in `self.messages`."""

    def __init__(self):
        self.messages: dict[str, dict] = {}
        self.labels: dict[str, str] = {}  # name -> id
        self.modify_calls: list[tuple[str, list[str]]] = []
        self.fail_modify_once = False
        self._ids = itertools.count(1)

    # ---- helpers for tests
    def add_raw(self, raw: bytes, label_ids=("INBOX", "UNREAD")) -> str:
        gid = f"g{next(self._ids):04d}"
        self.messages[gid] = {"id": gid, "threadId": f"t{gid}", "labelIds": list(label_ids),
                              "raw": base64.urlsafe_b64encode(raw).decode("ascii"), "internalDate": "1792000000000"}
        return gid

    def label_names(self, gid: str) -> set[str]:
        by_id = {v: k for k, v in self.labels.items()}
        return {by_id.get(lid, lid) for lid in self.messages[gid]["labelIds"]}

    # ---- messages
    def list(self, userId, q=None, pageToken=None, maxResults=100):  # noqa: N803 - Gmail API names
        excluded = {self.labels.get("AR-Processed"), self.labels.get("AR-Outbound"), self.labels.get("AR-Ignored")}
        ids = [{"id": m["id"]} for m in self.messages.values()
               if "INBOX" in m["labelIds"] and not excluded & set(m["labelIds"])]
        return _Call(lambda: {"messages": ids[:maxResults]})

    def get(self, userId, id, format="full"):  # noqa: A002
        return _Call(lambda: dict(self.messages[id]))

    def modify(self, userId, id, body):  # noqa: A002
        def run():
            if self.fail_modify_once:
                self.fail_modify_once = False
                raise RuntimeError("simulated Gmail outage while labelling")
            self.modify_calls.append((id, body.get("addLabelIds", [])))
            labels = self.messages[id]["labelIds"]
            for lid in body.get("addLabelIds", []):
                if lid not in labels:
                    labels.append(lid)
            for lid in body.get("removeLabelIds", []):
                if lid in labels:
                    labels.remove(lid)
            return {"id": id}
        return _Call(run)

    def import_(self, userId, body, media_body, **kwargs):
        raw = media_body.getbytes(0, media_body.size())
        gid = self.add_raw(raw, body.get("labelIds", []))
        self.last_import_kwargs = kwargs
        return _Call(lambda: {"id": gid, "threadId": f"t{gid}"})


class _FakeLabels:
    def __init__(self, gmail: FakeGmail):
        self.g = gmail

    def list(self, userId):  # noqa: N803
        return _Call(lambda: {"labels": [{"id": i, "name": n} for n, i in self.g.labels.items()]})

    def create(self, userId, body):  # noqa: N803
        def run():
            lid = f"Label_{len(self.g.labels) + 1}"
            self.g.labels[body["name"]] = lid
            return {"id": lid, "name": body["name"]}
        return _Call(run)


class _FakeUsers:
    def __init__(self, gmail: FakeGmail):
        self.g = gmail

    def messages(self):
        return self.g

    def labels(self):
        return _FakeLabels(self.g)


class FakeService:
    def __init__(self):
        self.gmail = FakeGmail()

    def users(self):
        return _FakeUsers(self.gmail)


@pytest.fixture
def fake_service():
    from app.gmail import client

    client._label_ids.clear()  # label ids are cached per process; each fake mailbox has its own
    return FakeService()
