"""What the classifier looks at - the same shape for stored e-mails and for sample folders."""
from dataclasses import dataclass, field
from datetime import date

LABELS = ("REMITTANCE", "PTP", "OUT_OF_SCOPE")

# Out-of-scope categories (prototype Knowledge Base, "Out-of-Scope Categories"); sample folders O01..O07
OOS_CATEGORIES = {
    "MARKETING": "Marketing communication",
    "CUSTOMER_SERVICE": "Customer service query",
    "SALES_INQUIRY": "Sales inquiry",
    "GENERAL": "General correspondence",
    "VENDOR_INVOICE": "Vendor invoice",
    "HR": "HR communication",
    "BANK_NOTIFICATION": "Bank notification unrelated to payment",
}


@dataclass
class Document:
    name: str
    text: str


@dataclass
class ClassifierInput:
    subject: str
    body: str                                   # body without quoted reply history
    attachments: list[Document] = field(default_factory=list)
    sender_email: str | None = None
    sender_known: bool | None = None            # sender address/domain found in ADR6 (None = not checked)
    business_date: date | None = None

    def all_text(self) -> str:
        parts = [self.subject, self.body] + [f"{d.name}\n{d.text}" for d in self.attachments]
        return "\n".join(p for p in parts if p)
