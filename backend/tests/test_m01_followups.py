"""M01 follow-ups: POLLER_ENABLED guard, admin key on /api/admin/*, live sample Date."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.gmail import parsing
from app.gmail.poller import PollerDisabled, poll
from app.gmail.sample_sender import build_message, load_sample
from app.main import app

client = TestClient(app)
KEY = "test-admin-key-0123456789"


# --------------------------------------------------------------------------- POLLER_ENABLED
def test_poller_refuses_when_disabled(db, storage, fake_service, monkeypatch):
    monkeypatch.setattr(get_settings(), "poller_enabled", False)
    fake_service.gmail.add_raw(build_message(load_sample("R01-0007")).as_bytes())
    with pytest.raises(PollerDisabled):
        poll(db, service=fake_service, storage=storage)
    assert fake_service.gmail.modify_calls == []  # nothing touched in Gmail


def test_poller_force_overrides(db, storage, fake_service, monkeypatch):
    monkeypatch.setattr(get_settings(), "poller_enabled", False)
    fake_service.gmail.add_raw(build_message(load_sample("R01-0007")).as_bytes())
    assert poll(db, service=fake_service, storage=storage, force=True).stored == 1


def test_default_setting_is_off():
    from app.config import Settings

    assert Settings.model_fields["poller_enabled"].default is False


# --------------------------------------------------------------------------- admin key
def test_admin_endpoints_off_without_configured_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", "")
    assert client.post("/api/admin/gmail/poll", headers={"X-Admin-Key": "anything"}).status_code == 403


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong"}, {"X-Admin-Key": KEY + "x"}])
def test_admin_endpoints_reject_missing_or_wrong_key(monkeypatch, headers):
    monkeypatch.setattr(get_settings(), "admin_api_key", KEY)
    r = client.post("/api/admin/gmail/poll", headers=headers)
    assert r.status_code == 401


def test_admin_endpoint_with_key_reaches_the_poller(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", KEY)
    monkeypatch.setattr(get_settings(), "poller_enabled", False)  # stop before any real Gmail call
    r = client.post("/api/admin/gmail/poll", headers={"X-Admin-Key": KEY})
    assert r.status_code == 409 and "POLLER_ENABLED" in r.json()["detail"]


def test_public_endpoints_need_no_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", KEY)
    assert client.get("/api/emails?limit=1").status_code == 200


def test_openapi_shows_the_admin_key():
    spec = client.get("/openapi.json").json()
    assert "X-Admin-Key" in str(spec["components"]["securitySchemes"])
    assert spec["paths"]["/api/admin/gmail/poll"]["post"]["security"]


# --------------------------------------------------------------------------- live sample Date
def test_live_send_is_dated_now_with_original_kept():
    now = datetime(2026, 10, 28, 9, 30, tzinfo=timezone.utc)
    p = parsing.parse_raw_email(build_message(load_sample("R01-0007"), now=now).as_bytes())
    assert p.date == now
    assert p.headers["x-original-date"] == "Fri, 23 Oct 2026 19:58:56 +0000"


def test_original_date_option_keeps_sample_date():
    p = parsing.parse_raw_email(build_message(load_sample("R01-0007"), original_date=True).as_bytes())
    assert p.date.isoformat() == "2026-10-23T19:58:56+00:00"
    assert "x-original-date" not in p.headers
