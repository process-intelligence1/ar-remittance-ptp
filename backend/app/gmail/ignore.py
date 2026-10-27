"""Ignored system senders (rule "ignored_senders" in ar.rule_config).

E-mails from these senders are NOT stored - no body, no files - only an audit entry and the
Gmail label AR-Ignored. The rule holds ONLY domains; a listed domain also covers its sub-domains.
There are deliberately no address patterns such as "noreply@*": automated senders can send
genuine remittances (sample R19-0112 comes from noreply@kangaroo-erp-mail.net).
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.ar import RuleConfig
from app.rules_defaults import IGNORED_SENDERS

REASON = "ignored system sender"


@dataclass(frozen=True)
class SenderIgnoreList:
    domains: tuple[str, ...]

    @classmethod
    def from_value(cls, value: dict | None) -> "SenderIgnoreList":
        value = value or {}
        return cls(tuple(d.strip().lower().lstrip("@.") for d in value.get("domains", []) if d.strip()))

    def match(self, address: str | None) -> str | None:
        """The rule that matches `address` (e.g. "domain github.com"), or None."""
        if not address or "@" not in address:
            return None
        domain = address.strip().lower().rsplit("@", 1)[1]
        for d in self.domains:
            if domain == d or domain.endswith("." + d):
                return f"domain {d}"
        return None

    def match_any(self, *addresses: str | None) -> str | None:
        for a in addresses:
            if rule := self.match(a):
                return rule
        return None


def load_ignore_list(db: Session) -> SenderIgnoreList:
    row = db.get(RuleConfig, "ignored_senders")
    return SenderIgnoreList.from_value(row.value if row else IGNORED_SENDERS)
