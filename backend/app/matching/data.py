"""In-memory views of the simulated SAP data used by matching (BSID ~5,000 rows, 71 customers).

Loaded once per run (`load_sap(db)`); amounts are signed (credit items, SHKZG = H, are negative).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.extraction.refs import normalise_ref


@dataclass(frozen=True)
class OpenItem:
    id: int
    bukrs: str
    kunnr: str
    belnr: str
    xblnr: str | None
    vbeln: str | None
    currency: str
    amount: Decimal          # signed: credit items (SHKZG = H) negative
    shkzg: str
    bldat: date              # document (invoice) date
    due: date | None         # baseline date (ZFBDT)
    blocked: bool            # payment block ZLSPR = R

    @property
    def is_credit(self) -> bool:
        return self.shkzg == "H"


@dataclass
class Customer:
    kunnr: str
    name: str                # NAME1 + NAME2
    country: str | None
    bukrs: set[str] = field(default_factory=set)


@dataclass
class SapData:
    items: dict[int, OpenItem]
    by_xblnr: dict[str, list[OpenItem]]
    by_belnr: dict[str, list[OpenItem]]
    by_vbeln: dict[str, list[OpenItem]]
    by_kunnr: dict[str, list[OpenItem]]
    customers: dict[str, Customer]
    by_address: dict[str, set[str]]       # e-mail address -> kunnr
    by_domain: dict[str, set[str]]        # e-mail domain -> kunnr
    by_iban: dict[str, set[str]]
    paid_by: dict[str, set[str]]          # payer (KNVP RG) -> customers it pays for

    def customer(self, kunnr: str | None) -> Customer | None:
        return self.customers.get(kunnr) if kunnr else None

    def find_kunnr(self, written: str | None) -> str | None:
        """A customer number as quoted ('102419') -> the KNA1 key ('0000102419')."""
        if not written:
            return None
        digits = written.strip().lstrip("0")
        for k in self.customers:
            if k.lstrip("0") == digits:
                return k
        return None


def load_sap(db: Session) -> SapData:
    items: dict[int, OpenItem] = {}
    by_x, by_b, by_v, by_k = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for r in db.execute(text("select id, bukrs, kunnr, belnr, xblnr, vbeln, waers, wrbtr, shkzg, bldat, zfbdt, zlspr "
                             "from sap.bsid")):
        amount = -r.wrbtr if r.shkzg == "H" else r.wrbtr
        it = OpenItem(r.id, r.bukrs, r.kunnr, r.belnr, r.xblnr, r.vbeln, r.waers, amount, r.shkzg, r.bldat, r.zfbdt,
                      (r.zlspr or "").upper() == "R")
        items[it.id] = it
        by_k[it.kunnr].append(it)
        for value, index in ((it.xblnr, by_x), (it.belnr, by_b), (it.vbeln, by_v)):
            n = normalise_ref(value)
            if n:
                index[n].append(it)
    customers = {r.kunnr: Customer(r.kunnr, " ".join(x for x in (r.name1, r.name2) if x), r.land1)
                 for r in db.execute(text("select kunnr, name1, name2, land1 from sap.kna1"))}
    for r in db.execute(text("select kunnr, bukrs from sap.knb1")):
        if r.kunnr in customers:
            customers[r.kunnr].bukrs.add(r.bukrs)
    by_addr, by_dom = defaultdict(set), defaultdict(set)
    for r in db.execute(text("select lower(a.smtp_addr) addr, k.kunnr from sap.adr6 a "
                             "join sap.kna1 k on k.adrnr = a.addrnumber where a.smtp_addr is not null")):
        by_addr[r.addr].add(r.kunnr)
        by_dom[r.addr.rsplit("@", 1)[-1]].add(r.kunnr)
    by_iban = defaultdict(set)
    for r in db.execute(text("select kunnr, upper(replace(iban, ' ', '')) iban from sap.knbk where iban is not null")):
        by_iban[r.iban].add(r.kunnr)
    paid_by = defaultdict(set)
    for r in db.execute(text("select kunnr, kunn2 from sap.knvp where parvw = 'RG' and kunn2 is not null")):
        if r.kunn2 != r.kunnr:
            paid_by[r.kunn2].add(r.kunnr)
    return SapData(items, dict(by_x), dict(by_b), dict(by_v), dict(by_k), customers, dict(by_addr), dict(by_dom),
                   dict(by_iban), dict(paid_by))
