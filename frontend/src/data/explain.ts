import type { WorkItemDetail } from "./types";

// Plain-language texts of the record detail, generated from the stored scores by fixed rules (no AI call).
// They live in the front-end so the demo edition (static snapshot) shows exactly the same.

export interface ScoreRow {
  key: string;
  name: string;
  description: string;
  weight: string;
  score: number; // 0..1
}

const num = (v: unknown): number | null => (v === null || v === undefined || v === "" ? null : Number(v));

export function confidenceRows(d: WorkItemDetail): ScoreRow[] {
  const s = d.score_breakdown;
  const invoice = num(s.invoice_match_score) ?? 0;
  const amount = num(s.amount_alignment_score) ?? 0;
  const sender = num(s.sender_company_score) ?? 0;
  const name = num(s.customer_name_similarity) ?? 0;
  const date = num(s.date_proxy_score) ?? 0;
  const diff = num(s.amount_difference_pct);
  const days = num(s.date_difference_days);
  const bsidInvoice = d.bsid?.invoice ?? null;
  const field = d.match_field ?? "XBLNR";

  let invoiceText: string;
  if (d.match_level === "EXACT") invoiceText = `Invoice number "${d.invoice_ref ?? "—"}" matches the BSID ${field} "${bsidInvoice ?? "—"}" exactly (after normalisation).`;
  else if (d.match_level === "NEAR") invoiceText = `Invoice number "${d.invoice_ref ?? "—"}" differs from BSID "${bsidInvoice ?? "—"}" by one character that OCR often confuses - possible OCR misread, always reviewed.`;
  else invoiceText = d.invoice_ref ? `Invoice number "${d.invoice_ref}" matches no open BSID item.` : "No invoice number was found in the e-mail.";

  const amountText = diff === null ? "The amount could not be compared with an open item (missing, or another currency)." : `The amount differs from the open item by ${Math.abs(diff).toFixed(3)} %.`;
  const senderText = sender >= 1 ? `The sender address is mapped to company code ${d.company_code ?? "—"}.` : "The sender address is not mapped to this company code.";
  const nameText = `The name in the e-mail is ${(name * 100).toFixed(0)} % similar to "${d.bsid?.customer_name ?? d.customer_name ?? "—"}".`;
  const dateText = days === null ? "No date was available to compare." : `${Math.abs(days)} day(s) between the invoice date and the payment date.`;

  return [
    { key: "invoice", name: `Invoice Number Match${d.match_level ? ` (${d.match_level})` : ""}`, description: invoiceText, weight: "35%", score: invoice },
    { key: "amount", name: "Amount Alignment", description: amountText, weight: "30%", score: amount },
    { key: "sender", name: "Sender → Company Code", description: senderText, weight: "10%", score: sender },
    { key: "name", name: "Customer Name Similarity", description: nameText, weight: "5%", score: name },
    { key: "date", name: "Date Proxy", description: dateText, weight: "10%", score: date },
  ];
}

/** The fast-path banner text, or null when no fast path applied. */
export function fastPathBanner(d: WorkItemDetail): string | null {
  const fp = d.score_breakdown.fast_path_override;
  if (!fp || fp === "No") return null;
  const value = String(fp).toUpperCase().includes("MISSING") ? 91 : 92;
  const condition = value === 91 ? "EXACT invoice match + open BSID item + same currency, amount missing" : "EXACT invoice match + open BSID item + same currency + amount within 2 %";
  return `Fast path: ${condition} → score set to at least ${value} %.`;
}

export function confidenceBadge(d: WorkItemDetail): { label: string; cls: string } {
  const c = d.score_breakdown.confidence_score === null ? null : Number(d.score_breakdown.confidence_score);
  if (c === null) return { label: "—", cls: "" };
  return c >= 80 ? { label: "High", cls: "badge-high" } : c >= 40 ? { label: "Medium", cls: "badge-medium" } : { label: "Low", cls: "badge-low" };
}

const kind = (d: WorkItemDetail) => {
  const c = d.classification === "DUPLICATE" && d.line_type ? d.line_type : d.classification; // a duplicate is still a remittance or a promise
  return c === "PTP" ? "promise to pay" : c === "REMITTANCE" ? "remittance" : c.toLowerCase().replace(/_/g, " ");
};

/** A short plain-language summary of what the system did with this row and why. */
export function aiExplanation(d: WorkItemDetail): string[] {
  const out: string[] = [];
  const s = d.score_breakdown;
  const conf = num(s.confidence_score);
  const who = d.customer_name ? `${d.customer_name} (${(d.kunnr ?? "").replace(/^0+/, "")})` : null;

  if (d.classification === "OUT_OF_SCOPE" || d.decision === "OUT_OF_SCOPE") {
    out.push("This e-mail is not about remittances or promises to pay, so it was set aside as out of scope and no invoice was matched.");
    return out;
  }
  out.push(`The e-mail was read as a ${kind(d)}${who ? ` from ${who}` : ""}${d.invoice_ref ? ` for invoice ${d.invoice_ref}` : ""}.`);

  if (d.match_level === "EXACT" && d.bsid?.matched) out.push(`The invoice number matches an open SAP item exactly${d.bsid.document ? ` (document ${d.bsid.document})` : ""}.`);
  else if (d.match_level === "NEAR") out.push("The invoice number is one OCR-confusable character away from an open SAP item, so it may be misread; a person should check it.");
  else if (!d.bsid?.matched) out.push("No open SAP item matches the invoice number.");

  const diff = num(s.amount_difference_pct);
  if (d.bsid?.matched && diff !== null) out.push(`The amount differs from the open item by ${Math.abs(diff).toFixed(3)} %.`);

  const fp = fastPathBanner(d);
  if (conf !== null) {
    const level = conf >= 80 ? "high" : conf >= 40 ? "medium" : "low";
    const source = d.confidence_source === "FAST_PATH" ? "the fast-path rule" : "the weighted score";
    out.push(`The confidence is ${conf.toFixed(1)} % (${level}), taken from ${source}${fp && d.confidence_source !== "FAST_PATH" ? " - the weighted score was higher than the fast-path value" : ""}.`);
  }

  if (d.duplicate_of) out.push(`It looks like a repeat of ${d.duplicate_of}, which was received earlier with the same values.`);
  if (d.exception_reason) out.push(`It is an exception: ${d.exception_reason}.`);
  if (d.review_reasons?.length) out.push(`It needs a person to look at it because: ${d.review_reasons.join("; ")}.`);
  if (d.status === "AUTO_PROCESSED") out.push("Everything lined up, so it was processed automatically.");
  else if (d.status === "CONFIRMED") out.push("It was confirmed and added to the Excel export list.");
  if (d.recommended_action) out.push(`Recommended next step: ${d.recommended_action}.`);
  return out;
}
