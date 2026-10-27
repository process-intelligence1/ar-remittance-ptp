"""Who is paying: customer identification for one e-mail.

Signals, strongest first (the first that gives exactly one customer wins; all are kept as evidence):
  INVOICE          invoice numbers that match BSID EXACTLY -> that item's customer (the majority)
  SENDER_ADDRESS   the sender's address in ADR6
  CUSTOMER_NUMBER  the customer number the payer quotes ("Your customer no. 102419" = KUNNR)
  IBAN             the payer's IBAN in KNBK
  SENDER_DOMAIN    the sender's domain in ADR6, when only one customer uses it
  NAME             payer name vs KNA1 NAME1 + NAME2 (difflib, legal forms removed), >= the threshold
Payer relationships (KNVP partner function RG) widen the search: a holding company that pays for its
subsidiaries (R20) may settle their open items.
"""
import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

from app.matching.data import SapData

METHOD_SCORE = {"INVOICE": 1.0, "SENDER_ADDRESS": 0.95, "CUSTOMER_NUMBER": 0.95, "IBAN": 0.9,
                "SENDER_DOMAIN": 0.8}
LEGAL = re.compile(r"\b(?:ltd|limited|gmbh|ag|inc|llc|plc|sas|sarl|sa|s\.a|sl|s\.l|ltda|pvt|private|pte|pty|kk|k\.k|"
                   r"co|corp|corporation|company|kg|bv|nv|ab|oy|spa|srl|de\s+c\.?v|cv|the)\b\.?")
PUBLIC_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "live.com",
                  "gmx.de", "web.de", "proton.me"}


def clean_name(name: str | None) -> str:
    n = (name or "").lower().replace("&", " and ")
    n = LEGAL.sub(" ", n)
    return re.sub(r"[^a-z0-9぀-ヿ一-鿿]+", " ", n).strip()


def name_similarity(a: str | None, b: str | None) -> float:
    """0..1 - difflib on the names without legal forms; word order does not matter."""
    x, y = clean_name(a), clean_name(b)
    if not x or not y:
        return 0.0
    direct = difflib.SequenceMatcher(None, x, y).ratio()
    sorted_words = difflib.SequenceMatcher(None, " ".join(sorted(x.split())), " ".join(sorted(y.split()))).ratio()
    contained = 0.95 if (len(x) >= 6 and x in y) or (len(y) >= 6 and y in x) else 0.0
    return round(max(direct, sorted_words, contained), 4)


@dataclass
class CustomerResult:
    kunnr: str | None
    method: str | None
    score: float
    evidence: dict = field(default_factory=dict)
    allowed: set[str] = field(default_factory=set)   # customers whose open items this payer may settle
    sender_customers: set[str] = field(default_factory=set)  # from the sender address / domain (for scoring)
    payer_customers: set[str] = field(default_factory=set)   # who SENT it: address, quoted number, IBAN, domain
    related: set[str] = field(default_factory=set)           # payer customers + those they pay for (KNVP RG)


def identify(sap: SapData, *, sender_email: str | None, customer_number: str | None, iban: str | None,
             payer_name: str | None, exact_invoice_customers: list[str], name_min: float) -> CustomerResult:
    ev: dict = {}
    addr = (sender_email or "").lower()
    domain = addr.rsplit("@", 1)[-1] if "@" in addr else None
    by_addr = sap.by_address.get(addr, set())
    by_dom = sap.by_domain.get(domain, set()) if domain and domain not in PUBLIC_DOMAINS else set()
    by_number = {k} if (k := sap.find_kunnr(customer_number)) else set()
    by_iban = sap.by_iban.get((iban or "").upper().replace(" ", ""), set())
    invoice = Counter(exact_invoice_customers)
    ev.update(invoice={k: n for k, n in invoice.items()} or None, sender_address=sorted(by_addr) or None,
              sender_domain=sorted(by_dom) or None, customer_number=sorted(by_number) or None,
              iban=sorted(by_iban) or None)

    names = sorted(((name_similarity(payer_name, c.name), k) for k, c in sap.customers.items()), reverse=True)[:3] \
        if payer_name else []
    ev["name"] = [{"kunnr": k, "similarity": s} for s, k in names] or None

    chosen, method, score = None, None, 0.0
    if invoice:
        top = invoice.most_common()
        if len(top) == 1 or top[0][1] > top[1][1]:
            chosen, method = top[0][0], "INVOICE"
    for m, cands in (("SENDER_ADDRESS", by_addr), ("CUSTOMER_NUMBER", by_number), ("IBAN", by_iban),
                     ("SENDER_DOMAIN", by_dom)):
        if chosen is None and len(cands) == 1:
            chosen, method = next(iter(cands)), m
    if chosen is None and names and names[0][0] >= name_min and (len(names) == 1 or names[0][0] > names[1][0]):
        chosen, method = names[0][1], "NAME"
    if method:
        score = names[0][0] if method == "NAME" else METHOD_SCORE[method]

    allowed: set[str] = set()
    for k in {chosen} | by_addr | by_number | by_iban | (by_dom if len(by_dom) <= 3 else set()) - {None}:
        if k:
            allowed |= {k} | sap.paid_by.get(k, set())
    payers = by_addr | by_number | by_iban | (by_dom if len(by_dom) <= 3 else set())
    related = set(payers)
    for k in payers:
        related |= sap.paid_by.get(k, set())
        related |= {c for c, ps in sap.paid_by.items() if k in ps}  # its own payer (parent) too
    return CustomerResult(chosen, method, score, ev, allowed, by_addr | (by_dom if len(by_dom) <= 3 else set()),
                          payers, related)
