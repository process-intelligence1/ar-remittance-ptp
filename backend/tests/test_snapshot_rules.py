"""M15: the shared fixture that keeps the browser's copies of the rules (frontend/src/data/permissions.ts, snapshot/templates.ts) equal to the
server's. If this test fails, a rule changed: regenerate data/eval/snapshot_rules_fixture.json (the generator is in the M15 notes) and update the
TypeScript copies - the front-end tests then check them against the new fixture."""
import json
from pathlib import Path

from app import outbound
from app.permissions import allowed_actions

FIXTURE = json.loads((Path(__file__).resolve().parents[2] / "data" / "eval" / "snapshot_rules_fixture.json").read_text(encoding="utf-8"))


def test_permission_fixture_matches_the_server_rules():
    assert len(FIXTURE["cases"]) == 2800
    wrong = [c for c in FIXTURE["cases"] if allowed_actions(c["role"], c["decision"], c["status"], c["assigned_role"], c["resolved"]) != c["allowed"]]
    assert wrong == []


def test_template_fixture_matches_the_server_templates():
    t = FIXTURE["templates"]
    assert t["default_question"] == outbound.DEFAULT_QUESTION
    for lang, tpl in outbound.TEMPLATES.items():
        c = {**t["ctx"], "question": outbound.DEFAULT_QUESTION[lang]}
        assert t["rendered"][lang] == {"subject": outbound._env.from_string(tpl["subject"]).render(**c), "body": outbound._env.from_string(tpl["body"]).render(**c)}
