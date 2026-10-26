"""SAP reference tables (schema "sap").

Generated once from the Excel files in data/seed, then kept as normal code.
Column names follow SAP (lower-case) so business users recognise them.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SCHEMA = "sap"


class Bsid(Base):
    """Open customer items (SAP BSID). One row per open invoice, credit note or payment line."""
    __tablename__ = "bsid"
    __table_args__ = (
        UniqueConstraint('mandt', 'bukrs', 'kunnr', 'gjahr', 'belnr', 'buzei', name="uq_bsid_key"),
        Index("ix_bsid_xblnr", "xblnr"),
        Index("ix_bsid_kunnr_bukrs", "kunnr", "bukrs"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    bukrs: Mapped[str] = mapped_column(String(4), nullable=False)
    kunnr: Mapped[str] = mapped_column(String(10), nullable=False)
    umsks: Mapped[str | None] = mapped_column(String(1), nullable=True)
    umskz: Mapped[str | None] = mapped_column(String(1), nullable=True)
    augdt: Mapped[date | None] = mapped_column(Date, nullable=True)
    augbl: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zuonr: Mapped[str | None] = mapped_column(String(18), nullable=True)
    gjahr: Mapped[int] = mapped_column(Integer, nullable=False)
    belnr: Mapped[str] = mapped_column(String(10), nullable=False)
    buzei: Mapped[int] = mapped_column(Integer, nullable=False)
    budat: Mapped[date | None] = mapped_column(Date, nullable=True)
    bldat: Mapped[date | None] = mapped_column(Date, nullable=True)
    cpudt: Mapped[date | None] = mapped_column(Date, nullable=True)
    waers: Mapped[str | None] = mapped_column(String(3), nullable=True)
    xblnr: Mapped[str | None] = mapped_column(String(16), nullable=True)
    blart: Mapped[str | None] = mapped_column(String(2), nullable=True)
    monat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bschl: Mapped[str | None] = mapped_column(String(2), nullable=True)
    shkzg: Mapped[str | None] = mapped_column(String(1), nullable=True)
    gsber: Mapped[str | None] = mapped_column(String(4), nullable=True)
    wrbtr: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    dmbtr: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    dmbe2: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    mwskz: Mapped[str | None] = mapped_column(String(2), nullable=True)
    wmwst: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    sgtxt: Mapped[str | None] = mapped_column(String(80), nullable=True)
    zfbdt: Mapped[date | None] = mapped_column(Date, nullable=True)
    zterm: Mapped[str | None] = mapped_column(String(4), nullable=True)
    zbd1t: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd2t: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd3t: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd1p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd2p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    netdt: Mapped[date | None] = mapped_column(Date, nullable=True)
    skfbt: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    wskto: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    zlsch: Mapped[str | None] = mapped_column(String(1), nullable=True)
    zlspr: Mapped[str | None] = mapped_column(String(1), nullable=True)
    manst: Mapped[int | None] = mapped_column(Integer, nullable=True)
    madat: Mapped[date | None] = mapped_column(Date, nullable=True)
    mansp: Mapped[str | None] = mapped_column(String(1), nullable=True)
    vbeln: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rebzg: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rebzj: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rebzz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xref1: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xref2: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xref3: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hkont: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prctr: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kkber: Mapped[str | None] = mapped_column(String(4), nullable=True)


class Bsad(Base):
    """Cleared customer items (SAP BSAD). Items move here from BSID when a payment is applied."""
    __tablename__ = "bsad"
    __table_args__ = (
        UniqueConstraint('mandt', 'bukrs', 'kunnr', 'gjahr', 'belnr', 'buzei', name="uq_bsad_key"),
        Index("ix_bsad_xblnr", "xblnr"),
        Index("ix_bsad_kunnr_bukrs", "kunnr", "bukrs"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    bukrs: Mapped[str] = mapped_column(String(4), nullable=False)
    kunnr: Mapped[str] = mapped_column(String(10), nullable=False)
    umsks: Mapped[str | None] = mapped_column(String(1), nullable=True)
    umskz: Mapped[str | None] = mapped_column(String(1), nullable=True)
    augdt: Mapped[date | None] = mapped_column(Date, nullable=True)
    augbl: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zuonr: Mapped[str | None] = mapped_column(String(18), nullable=True)
    gjahr: Mapped[int] = mapped_column(Integer, nullable=False)
    belnr: Mapped[str] = mapped_column(String(10), nullable=False)
    buzei: Mapped[int] = mapped_column(Integer, nullable=False)
    budat: Mapped[date | None] = mapped_column(Date, nullable=True)
    bldat: Mapped[date | None] = mapped_column(Date, nullable=True)
    cpudt: Mapped[date | None] = mapped_column(Date, nullable=True)
    waers: Mapped[str | None] = mapped_column(String(3), nullable=True)
    xblnr: Mapped[str | None] = mapped_column(String(16), nullable=True)
    blart: Mapped[str | None] = mapped_column(String(2), nullable=True)
    monat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bschl: Mapped[str | None] = mapped_column(String(2), nullable=True)
    shkzg: Mapped[str | None] = mapped_column(String(1), nullable=True)
    gsber: Mapped[str | None] = mapped_column(String(4), nullable=True)
    wrbtr: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    dmbtr: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    dmbe2: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    mwskz: Mapped[str | None] = mapped_column(String(2), nullable=True)
    wmwst: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    sgtxt: Mapped[str | None] = mapped_column(String(80), nullable=True)
    zfbdt: Mapped[date | None] = mapped_column(Date, nullable=True)
    zterm: Mapped[str | None] = mapped_column(String(4), nullable=True)
    zbd1t: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd2t: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd3t: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd1p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zbd2p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    netdt: Mapped[date | None] = mapped_column(Date, nullable=True)
    skfbt: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    wskto: Mapped[Decimal | None] = mapped_column(Numeric(17, 3), nullable=True)
    zlsch: Mapped[str | None] = mapped_column(String(1), nullable=True)
    zlspr: Mapped[str | None] = mapped_column(String(1), nullable=True)
    manst: Mapped[int | None] = mapped_column(Integer, nullable=True)
    madat: Mapped[date | None] = mapped_column(Date, nullable=True)
    mansp: Mapped[str | None] = mapped_column(String(1), nullable=True)
    vbeln: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rebzg: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rebzj: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rebzz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xref1: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xref2: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xref3: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hkont: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prctr: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kkber: Mapped[str | None] = mapped_column(String(4), nullable=True)


class Kna1(Base):
    """Customer master - general data (name, country, language)."""
    __tablename__ = "kna1"
    __table_args__ = (UniqueConstraint('mandt', 'kunnr', name="uq_kna1_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    kunnr: Mapped[str] = mapped_column(String(10), nullable=False)
    name1: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name2: Mapped[str | None] = mapped_column(String(80), nullable=True)
    land1: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ort01: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pstlz: Mapped[str | None] = mapped_column(String(10), nullable=True)
    stras: Mapped[str | None] = mapped_column(String(80), nullable=True)
    regio: Mapped[str | None] = mapped_column(String(3), nullable=True)
    spras: Mapped[str | None] = mapped_column(String(1), nullable=True)
    telf1: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stceg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    adrnr: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ktokd: Mapped[str | None] = mapped_column(String(4), nullable=True)
    brsch: Mapped[str | None] = mapped_column(String(4), nullable=True)
    erdat: Mapped[date | None] = mapped_column(Date, nullable=True)
    sortl: Mapped[str | None] = mapped_column(String(10), nullable=True)


class Knb1(Base):
    """Customer master - company-code data (which company codes a customer belongs to)."""
    __tablename__ = "knb1"
    __table_args__ = (UniqueConstraint('mandt', 'kunnr', 'bukrs', name="uq_knb1_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    kunnr: Mapped[str] = mapped_column(String(10), nullable=False)
    bukrs: Mapped[str] = mapped_column(String(4), nullable=False)
    akont: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zterm: Mapped[str | None] = mapped_column(String(4), nullable=True)
    zwels: Mapped[str | None] = mapped_column(String(2), nullable=True)
    busab: Mapped[str | None] = mapped_column(String(2), nullable=True)
    fdgrv: Mapped[str | None] = mapped_column(String(2), nullable=True)
    xzver: Mapped[str | None] = mapped_column(String(1), nullable=True)
    erdat: Mapped[date | None] = mapped_column(Date, nullable=True)
    loevm: Mapped[str | None] = mapped_column(String(1), nullable=True)


class Knbk(Base):
    """Customer bank details."""
    __tablename__ = "knbk"
    __table_args__ = (UniqueConstraint('mandt', 'kunnr', 'banks', 'bankl', 'bankn', name="uq_knbk_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    kunnr: Mapped[str] = mapped_column(String(10), nullable=False)
    banks: Mapped[str] = mapped_column(String(2), nullable=False)
    bankl: Mapped[str] = mapped_column(String(12), nullable=False)
    bankn: Mapped[str] = mapped_column(String(16), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    koinh: Mapped[str | None] = mapped_column(String(80), nullable=True)
    banka: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Knvp(Base):
    """Customer partner functions (sold-to, payer, bill-to)."""
    __tablename__ = "knvp"
    __table_args__ = (UniqueConstraint('mandt', 'kunnr', 'vkorg', 'vtweg', 'spart', 'parvw', 'parza', name="uq_knvp_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    kunnr: Mapped[str] = mapped_column(String(10), nullable=False)
    vkorg: Mapped[str] = mapped_column(String(4), nullable=False)
    vtweg: Mapped[str] = mapped_column(String(2), nullable=False)
    spart: Mapped[str] = mapped_column(String(2), nullable=False)
    parvw: Mapped[str] = mapped_column(String(2), nullable=False)
    parza: Mapped[str] = mapped_column(String(3), nullable=False)
    kunn2: Mapped[str | None] = mapped_column(String(10), nullable=True)


class Adr6(Base):
    """Customer e-mail addresses (linked to KNA1 via ADRNR = ADDRNUMBER)."""
    __tablename__ = "adr6"
    __table_args__ = (
        UniqueConstraint('client', 'addrnumber', 'consnumber', name="uq_adr6_key"),
        Index("ix_adr6_smtp_addr", "smtp_addr"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client: Mapped[str] = mapped_column(String(3), nullable=False)
    addrnumber: Mapped[str] = mapped_column(String(10), nullable=False)
    consnumber: Mapped[str] = mapped_column(String(3), nullable=False)
    smtp_addr: Mapped[str | None] = mapped_column(String(241), nullable=True)
    flgdefault: Mapped[str | None] = mapped_column(String(1), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(60), nullable=True)


class T001(Base):
    """Company codes (the Acme legal entities)."""
    __tablename__ = "t001"
    __table_args__ = (UniqueConstraint('mandt', 'bukrs', name="uq_t001_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    bukrs: Mapped[str] = mapped_column(String(4), nullable=False)
    butxt: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ort01: Mapped[str | None] = mapped_column(String(60), nullable=True)
    land1: Mapped[str | None] = mapped_column(String(2), nullable=True)
    waers: Mapped[str | None] = mapped_column(String(3), nullable=True)
    spras: Mapped[str | None] = mapped_column(String(1), nullable=True)
    ktopl: Mapped[str | None] = mapped_column(String(4), nullable=True)
    periv: Mapped[str | None] = mapped_column(String(2), nullable=True)
    stceg: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Tcurx(Base):
    """Currency decimal places."""
    __tablename__ = "tcurx"
    __table_args__ = (UniqueConstraint('currkey', name="uq_tcurx_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    currkey: Mapped[str] = mapped_column(String(3), nullable=False)
    currdec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ltext: Mapped[str | None] = mapped_column(String(60), nullable=True)


class T052(Base):
    """Payment terms."""
    __tablename__ = "t052"
    __table_args__ = (UniqueConstraint('mandt', 'zterm', name="uq_t052_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    zterm: Mapped[str] = mapped_column(String(4), nullable=False)
    text1: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ztag1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zprz1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ztag2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zprz2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ztag3: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Tcurr(Base):
    """Exchange rates."""
    __tablename__ = "tcurr"
    __table_args__ = (UniqueConstraint('mandt', 'kurst', 'fcurr', 'tcurr', 'gdatu', name="uq_tcurr_key"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandt: Mapped[str] = mapped_column(String(3), nullable=False)
    kurst: Mapped[str] = mapped_column(String(1), nullable=False)
    fcurr: Mapped[str] = mapped_column(String(3), nullable=False)
    tcurr: Mapped[str] = mapped_column(String(3), nullable=False)
    gdatu: Mapped[date] = mapped_column(Date, nullable=False)
    ukurs: Mapped[Decimal | None] = mapped_column(Numeric(15, 5), nullable=True)
    ffact: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tfact: Mapped[int | None] = mapped_column(Integer, nullable=True)


class FieldCatalog(Base):
    """Field descriptions from the Excel "Field_Descriptions" sheets (used for tooltips and the Knowledge Base)."""
    __tablename__ = "field_catalog"
    __table_args__ = (UniqueConstraint("source_table", "field", name="uq_field_catalog"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_table: Mapped[str] = mapped_column(String(20))
    field: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
