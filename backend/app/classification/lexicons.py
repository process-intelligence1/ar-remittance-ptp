"""Multilingual keyword lists (EN / DE / FR / ES / PT / JA).

Every entry is (name, regular expression, weight). Patterns run on folded text: lower case,
German umlauts written out (ü -> ue, ß -> ss), accents removed (é -> e), full-width characters
made normal. Japanese is matched as written (no word boundaries there).

Weights: 3 = on its own says what the e-mail is ("remittance advice", "we will pay");
2 = strong hint; 1 = supporting hint (also common in other kinds of mail).
To add a phrase, add a line here and run `python -m scripts.evaluate --stage classification`.
"""

# Payment already made -> REMITTANCE
REMITTANCE = [
    # English
    ("remittance advice", r"\bremittance\s+(advice|details|notice|notification)\b", 3),
    ("remittance", r"\bremittance\b", 2),
    ("payment advice", r"\bpayment\s+(advice|notification|notice|confirmation)\b", 3),
    ("we have paid", r"\bwe\s+have\s+((now|today|just|already|this\s+morning)\s+)?(paid|made|transferred|remitted|initiated|released|settled|processed)\b", 3),
    ("has been paid", r"\b(has|have|was|were)\s+(been\s+)?(paid|transferred|remitted|released|credited|processed|sent|settled)\b", 3),
    ("payment sent", r"\bpayment\s+(sent|released|made|executed|processed|transferred)\b", 3),
    ("funds sent", r"\bfunds\b(?:[^.\n]|\.(?=\S)){0,80}\b((have|has|were|was)\s+(been\s+)?(sent|transferred|released|remitted|credited)|left\s+our\s+account)\b", 3),
    ("we transferred", r"\bwe\s+(transferred|remitted|paid|wired|released)\b", 3),
    ("invoices settled", r"\b(invoices?|items?)\s+(settled|paid)\b", 2),
    ("amount paid", r"\b(amount|total|sum)\s+paid\b", 2),
    ("payment made", r"\bpayment\s+made\b|\b(latest|last)\s+payment\s+run\b", 2),
    ("proof of payment", r"\bproof\s+of\s+(payment|transfer)\b|\btransfer\s+(executed|completed|confirmation)\b", 3),
    ("paid today", r"\bpaid\s+(today|yesterday|on)\b", 2),
    ("bank transfer", r"\b(wire|bank|telegraphic)\s+transfer\b|\bneft\b|\brtgs\b|\bach\s+credit\b", 1),
    ("payment reference", r"\bpayment\s+(reference|ref|date|method)\b", 1),
    # German
    ("zahlungsavis", r"zahlungsavis|zahlungsanzeige|zahlungsbestaetigung|ueberweisungsbestaetigung", 3),
    ("zahlung veranlasst", r"zahlung\w*\s+(veranlasst|ausgefuehrt|freigegeben|angewiesen)|wurde\s+heute\s+freigegeben", 3),
    ("ueberwiesen", r"\bueberwiesen\b|\bhaben\b(?:[^.\n]|\.(?=\S)){0,100}\b(bezahlt|gezahlt|beglichen)\b", 3),
    ("wurde angewiesen", r"\bwurden?\b(?:[^.\n]|\.(?=\S)){0,80}\b(angewiesen|ueberwiesen|bezahlt|beglichen)\b", 3),
    ("ueberweisung", r"ueberweisung", 1),
    ("zahlbetrag", r"zahlbetrag|gezahlter\s+betrag|zahlungsreferenz|zahlungsdatum", 1),
    # French
    ("avis de paiement", r"avis\s+de\s+(paiement|virement|reglement)", 3),
    ("nous avons regle", r"nous\s+avons\s+(regle|paye|vire|effectue|procede)", 3),
    ("paiement effectue", r"(paiement|virement|reglement)\s+(effectue|execute|emis|realise)", 3),
    ("montant regle", r"montant\s+(regle|paye|vire)|total\s+regle", 2),
    ("a ete payee", r"\b(a|ont)\s+ete\s+(paye|regle|vire)e?s?\b", 3),
    ("virement", r"\bvirement\b", 1),
    # Spanish
    ("aviso de pago", r"aviso\s+de\s+(pago|transferencia)", 3),
    ("hemos pagado", r"hemos\s+(pagado|realizado|transferido|efectuado|abonado)", 3),
    ("importe pagado", r"(importe|total)\s+(pagado|abonado)", 2),
    ("pago factura", r"(?<!de )\bpago\s+(de\s+la\s+)?factura", 2),  # not "compromiso de pago factura"
    ("comprobante", r"comprobante\s+de\s+(la\s+)?(transferencia|pago)|\b(ha|han)\s+sido\s+pagad[oa]s?|\bfue(ron)?\s+pagad[oa]s?", 3),
    ("transferencia", r"transferencia", 1),
    # Portuguese
    ("aviso de pagamento", r"aviso\s+de\s+pagamento|comprovante\s+de\s+pagamento", 3),
    ("pagamento efetuado", r"pagamento\s+(efetuado|realizado)|efetuamos\s+o\s+pagamento|realizamos\s+o\s+pagamento", 3),
    ("valor pago", r"(valor|total)\s+pago\b", 2),
    ("foi paga", r"\bfo(i|ram)\s+pag[oa]s?\b", 3),
    # Japanese
    ("振込通知", r"振込通知|お振込みのご連絡|お振込のご連絡|送金通知|支払通知|支払明細", 3),
    ("振込みました", r"(振|ふ)り?込み?(いたしました|しました|済|完了)|お支払い(いたしました|しました)|送金(いたしました|しました)", 3),
    ("振込金額", r"振込金額|支払金額|振込日", 1),
]

# Payment promised for later -> PTP
PTP = [
    # English
    ("we will pay", r"\bwe\s+(will|shall|are\s+going\s+to|intend\s+to|plan\s+to|expect\s+to)\s+(pay|settle|clear|transfer|remit|release)\b", 3),
    ("will be paid", r"\bwill\s+be\s+(paid|settled|cleared|transferred|remitted|released)\b", 3),
    ("we commit", r"\b(we\s+)?commit(ment)?\s+to\s+(clearing|paying|settling|pay|settle|clear)\b", 3),
    ("payment commitment", r"\bpayment\s+(commitment|promise|plan|schedule|arrangement)\b|\bpromise[sd]?\s+to\s+pay\b|\bpromised\s+date\b", 3),
    ("is scheduled for", r"\b(is|are)\s+scheduled\s+(for|on)\b|\bscheduled\s+for\s+payment\b", 3),
    # "in instalments:" is a plan; "First instalment - balance to follow" (R07) is a part-payment made
    ("instalment plan", r"\bin\s+instal+ments\b|\binstal+ment\s+(plan|schedule)\b|\bin\s+(two|three|four|\d)\s+(parts|tranches)\b", 3),
    ("instalment", r"\binstal+ments?\b", 1),
    ("propose to settle", r"\bpropose\s+to\s+(pay|settle)\b|\bconfirm\s+this\s+schedule\b", 3),
    ("expect payment", r"\b(you\s+can\s+)?expect\s+(our\s+)?payment\b|\bpayment\s+(is\s+)?(planned|expected|due\s+to\s+go\s+out)\s+(on|for|by)\b", 3),
    ("next payment run", r"\b(next|our)\s+payment\s+run\s+(is|on)\b|\bincluded\s+in\s+(our|the)\s+(next\s+)?payment\s+run\b", 3),
    ("will follow on", r"\bwill\s+follow\s+(on|by)\b", 3),
    ("remaining invoices", r"\b(remaining|outstanding|balance\s+of\s+the)\s+invoices?\b", 2),
    ("reminder reply", r"\b(your|the)\s+(payment\s+)?reminder\b|\boverdue\s+reminder\b|\bapologies\s+for\s+the\s+delay\b", 1),
    # German
    ("zahlungszusage", r"zahlungszusage|zahlungsversprechen|zahlungsplan|ratenzahlung|zahlungsvereinbarung", 3),
    ("werden begleichen", r"\bwerden\b(?:[^.\n]|\.(?=\S)){0,120}\b(begleichen|bezahlen|zahlen|ueberweisen)\b|\b(begleichen|bezahlen|ueberweisen|zahlen)\s+wir\s+(am|bis)\b", 3),
    ("voraussichtlich", r"voraussichtlich\s+am|erfolgt\s+voraussichtlich|\bwird\b(?:[^.\n]|\.(?=\S)){0,80}\b(bezahlt|ueberwiesen|beglichen)\s+werden\b|\bgeplant\s+(fuer|am)\b", 3),
    ("restlichen rechnungen", r"restlichen\s+rechnung|offenen\s+rechnungen\s+begleichen", 2),
    ("mahnung", r"\bmahnung\b|\berinnerung\b|zahlungstermin", 1),
    # French
    ("engagement de paiement", r"engagement\s+de\s+(paiement|reglement)|echeancier|plan\s+de\s+paiement", 3),
    ("nous paierons", r"nous\s+(paierons|reglerons|effectuerons|allons\s+(payer|regler))|sera\s+(paye|regle)e?s?|seront\s+(payees?|reglees?)", 3),
    ("est prevu", r"\b(est|sont)\s+prevue?s?\s+(pour|le)\b|\bsera\s+effectue\s+le\b", 3),
    ("confirmons le reglement", r"confirmons\s+le\s+reglement", 2),
    ("relance", r"\brelance\b", 1),
    # Spanish
    ("compromiso de pago", r"compromiso\s+de\s+pago|plan\s+de\s+pagos?|calendario\s+de\s+pagos?", 3),
    ("realizaremos el pago", r"realizaremos|pagaremos|abonaremos|efectuaremos\s+el\s+pago|sera(n)?\s+pagad[oa]s?", 3),
    ("se pagara", r"\bse\s+pagar(a|an)\b|\b(esta|estan)\s+(previsto|programado)s?\s+para\b", 3),
    # Portuguese
    ("compromisso de pagamento", r"compromisso\s+de\s+pagamento|plano\s+de\s+pagamento|parcelamento", 3),
    ("esta programado", r"\b(esta|estao)\s+(programad|previst)[oa]s?\s+para\b|\bprevisto\s+para\b|\bsera\s+efetuado\b", 3),
    ("efetuaremos", r"efetuaremos|pagaremos|realizaremos|sera(o)?\s+pag[oa]s?", 3),
    # Japanese
    ("お支払い予定", r"(支払|お支払い?|振込み?|お振込み?)予定|予定でございます|分割(払い|でのお支払い)", 3),
    ("お支払いが遅れ", r"(支払|お支払い)が遅れ", 1),
]

# Out of scope, one list per category (prototype Knowledge Base, "Out-of-Scope Categories")
OUT_OF_SCOPE = {
    "MARKETING": [
        ("unsubscribe", r"\bunsubscribe\b|abmelden|desabonner|darse\s+de\s+baja|descadastrar|配信停止", 3),
        ("newsletter", r"\bnewsletter\b|\bexclusive\s+offers?\b|\bearly[-\s]bird\b|\bregister\s+now\b|\bwebinar\b", 3),
        ("promotion", r"\bdiscount\b|\bpromotion\b|\bproduct\s+launch(es)?\b|\bspecial\s+offer\b|\bdear\s+subscriber\b", 2),
    ],
    "CUSTOMER_SERVICE": [
        ("damaged goods", r"\bdamaged\b|\bdefective\b|\bbroken\s+on\s+arrival\b|beschaedigt|endommage|danad[oa]|破損", 3),
        ("replacement", r"\breplacement\b|\breturn\s+(authori[sz]ation|the\s+goods)\b|\bwrong\s+(item|goods)\b|\bmissing\s+items?\b", 2),
        ("complaint", r"\bcomplaint\b|\bsupport\s+ticket\b|\bservice\s+team\b|\bquality\s+issue\b|reklamation|reclamation|reclamacion|reclamacao", 2),
    ],
    "SALES_INQUIRY": [
        ("request for quotation", r"\brfq\b|\brequest\s+for\s+(a\s+)?(quote|quotation|proposal)\b|\bplease\s+quote\b|angebotsanfrage|demande\s+de\s+devis|solicitud\s+de\s+cotizacion|見積", 3),
        ("price / lead time", r"\bprice\s+list\b|\blead\s+time\b|\bquotation\b|\bunits\s+of\s+item\b|\bsales\s+team\b", 2),
    ],
    "GENERAL": [
        ("invitation", r"\binvitation\b|\binvite\b|\bmeet-?up\b|\bconfirm\s+(your\s+)?attendance\b|\bconference\b|einladung|\bjoin\s+our\b", 3),
        ("meeting request", r"\bmeeting\s+request\b|\bintroduc(e|tion|tory)\b|\bcatch[-\s]up\s+call\b|\bnetworking\b", 2),
    ],
    "VENDOR_INVOICE": [
        ("bill to", r"\bbill(ed)?\s+to\s*:?\s*acme\b|\binvoice\s+to\s*:?\s*acme\b", 3),
        ("amount due", r"\bamount\s+due\b|\bdue\s+within\s+\d+\s+days\b|\bnet\s+\d{2}\b|\bpayment\s+due\s+(date|by)\b|zahlbar\s+innerhalb", 2),
        ("tax invoice", r"\btax\s+invoice\b|\binvoice\s+\S+\s+from\b|\bplease\s+find\s+attached\s+(our\s+)?invoice\b|\bdear\s+customer\b", 2),
    ],
    "HR": [
        ("payslip", r"\bpayslip\b|\bpay\s+slip\b|\bsalary\b|\bpayroll\b|gehaltsabrechnung|bulletin\s+de\s+salaire|給与明細", 3),
        ("job application", r"\bapplication\s+for\b|\bcurriculum\s+vitae\b|\bresume\b|\bcandidate\b|\bvacancy\b|\bhr\s+team\b|\b(accountant|manager|analyst|engineer)\s+(role|position)\b", 2),
    ],
    "BANK_NOTIFICATION": [
        ("statement ready", r"\b(e-?)?statement\s+(is\s+)?(ready|available)\b|\bmonthly\s+statement\b|\bonline\s+banking\b|kontoauszug", 3),
        ("fx / balance alert", r"\bfx\s+rate\b|\balert\s+level\b|\bbalance\s+alert\b|\bexchange\s+rate\s+alert\b|\bdear\s+client\b", 2),
        ("automated message", r"\bautomated\s+message\b|\bdo\s+not\s+reply\b", 1),
    ],
}

# Attachment file names (folded, '_' and '-' read as spaces)
ATTACHMENT_NAMES = {
    "REMITTANCE": [
        ("advice file", r"remittance|payment\s?advice|paymentnotice|payment\s?notice|zahlungsavis|avis\s?de\s?(paiement|virement)|aviso\s?de\s?(pago|pagamento)|^ra\b|furikomi|振込", 2),
    ],
    "PTP": [
        ("commitment file", r"\bptp\b|commitment|promise|zahlungszusage|engagement|compromis+o|shiharai\s?yotei|予定", 2),
    ],
    "VENDOR_INVOICE": [
        ("invoice file", r"^(sinv|inv|invoice|rechnung|facture|factura)\b", 1),
    ],
}

# Shapes of payment references and invoice numbers (seen in the samples / BSID XBLNR)
PAYMENT_REFERENCE = (r"\b(PAY\d{5,}|ZA-\d{4,}|PV\d{5,}|RA-20\d\d-\d{3,}|REM-\S+|TRF\d{6,}|E2E-\d{6,}|UTR\d{8,}|"
                     r"ACH\d{6,}|FT\d{8,}|\d{4}[-/]\d{3})\b")
INVOICE_REFERENCE = (r"\b([A-Z]{3}/\d{4}/\d{5}|[A-Z]{2}-\d{2}-\d{6}|[A-Z]{2}-\d{7}|[A-Z]{2}\d{4}-\d{5}|"
                     r"[A-Z]{3}-\d{6}|[A-Z]{2}\d{8}|9\d{7}|\d{10})\b")
AMOUNT = (r"(?:[$€£¥₹₩]|\b(?:USD|EUR|GBP|JPY|INR|CHF|SGD|AUD|CAD|BRL|MXN|KWD|KD|AED|SEK|KRW|CNY|Rs\.?|R\$|S\$|US\$)\s?)"
          r"\s?\d[\d.,' ]*\d|\d[\d.,' ]*\d\s?(?:€|円|EUR|USD|GBP|JPY|INR|CHF|BRL|KWD)\b")
