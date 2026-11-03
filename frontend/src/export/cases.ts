import type { ExportedCase } from "../data";

// What the "Exported cases" Excel view shows and the downloaded .xlsx contains: ALL confirmed cases, same columns in both.

type Cell = string | number | Date | null;
export type CellKind = "text" | "number" | "date" | "datetime" | "percent";

export interface Column {
  header: string;
  width: number;
  kind: CellKind;
  get: (c: ExportedCase) => Cell;
}

const date = (v: string | null): Date | null => {
  if (!v) return null;
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d;
};

export const COLUMNS: Column[] = [
  { header: "Entry ID", width: 14, kind: "text", get: (c) => c.entry_id },
  { header: "Email ID", width: 14, kind: "text", get: (c) => c.email_ref },
  { header: "Received", width: 18, kind: "datetime", get: (c) => date(c.received_at) },
  { header: "Sender", width: 30, kind: "text", get: (c) => c.sender_email },
  { header: "Customer No.", width: 13, kind: "text", get: (c) => c.kunnr },
  { header: "Customer Name", width: 30, kind: "text", get: (c) => c.customer_name },
  { header: "Company Code", width: 13, kind: "text", get: (c) => c.company_code },
  { header: "Invoice No.", width: 18, kind: "text", get: (c) => c.invoice_ref },
  { header: "BSID Document (BELNR / GJAHR / BUZEI)", width: 34, kind: "text", get: (c) => (c.belnr ? `${c.belnr} / ${c.gjahr ?? ""} / ${c.buzei ?? ""}` : null) },
  { header: "Invoice Amount", width: 16, kind: "number", get: (c) => c.invoice_amount },
  { header: "Invoice Currency", width: 10, kind: "text", get: (c) => c.invoice_currency },
  { header: "Paid Amount", width: 16, kind: "number", get: (c) => c.paid_amount },
  { header: "Paid Currency", width: 10, kind: "text", get: (c) => c.paid_currency },
  { header: "Difference", width: 14, kind: "number", get: (c) => c.difference },
  { header: "Payment Date", width: 13, kind: "date", get: (c) => date(c.payment_date) },
  { header: "Payment Reference", width: 22, kind: "text", get: (c) => c.payment_reference },
  { header: "Match Level", width: 12, kind: "text", get: (c) => c.match_level },
  { header: "Confidence (%)", width: 13, kind: "percent", get: (c) => c.confidence },
  { header: "Decision", width: 22, kind: "text", get: (c) => c.decision },
  { header: "Confirmed By", width: 28, kind: "text", get: (c) => c.confirmed_by },
  { header: "Confirmed At", width: 18, kind: "datetime", get: (c) => date(c.confirmed_at) },
  { header: "Comment", width: 36, kind: "text", get: (c) => c.comment },
];

export const SUMMARY_HEADERS = ["Customer No.", "Customer Name", "Currency", "Cases", "Invoice Amount", "Paid Amount", "Difference"];

export interface SummaryRow {
  kunnr: string;
  customer: string;
  currency: string;
  cases: number;
  invoice: number;
  paid: number;
  difference: number;
}

/** Totals per customer AND currency (currencies are never added together). */
export function summarise(items: ExportedCase[]): SummaryRow[] {
  const groups = new Map<string, SummaryRow>();
  for (const c of items) {
    const currency = c.paid_currency ?? c.invoice_currency ?? "";
    const key = `${c.kunnr ?? ""}|${currency}`;
    const g = groups.get(key) ?? { kunnr: c.kunnr ?? "", customer: c.customer_name ?? "(unidentified)", currency, cases: 0, invoice: 0, paid: 0, difference: 0 };
    g.cases += 1;
    g.invoice += c.invoice_amount ?? 0;
    g.paid += c.paid_amount ?? 0;
    g.difference += c.difference ?? 0;
    groups.set(key, g);
  }
  const r = (n: number) => Math.round(n * 1000) / 1000;
  return [...groups.values()]
    .map((g) => ({ ...g, invoice: r(g.invoice), paid: r(g.paid), difference: r(g.difference) }))
    .sort((a, b) => a.customer.localeCompare(b.customer) || a.currency.localeCompare(b.currency));
}

export function summaryCells(s: SummaryRow): Cell[] {
  return [s.kunnr, s.customer, s.currency, s.cases, s.invoice, s.paid, s.difference];
}

const FORMATS: Record<CellKind, string | undefined> = { text: undefined, number: "#,##0.00", date: "yyyy-mm-dd", datetime: "yyyy-mm-dd hh:mm", percent: "0.0" };

/** The workbook: sheet "Cases" (one row per confirmed case) and sheet "Summary" (totals per customer and currency). */
export async function buildWorkbook(items: ExportedCase[]): Promise<ArrayBuffer> {
  const { default: ExcelJS } = await import("exceljs"); // loaded only when somebody downloads
  const wb = new ExcelJS.Workbook();
  wb.creator = "AR Remittance demo";
  const header = (ws: import("exceljs").Worksheet) => {
    const row = ws.getRow(1);
    row.font = { bold: true, color: { argb: "FFFFFFFF" } };
    row.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF217346" } };
    ws.views = [{ state: "frozen", ySplit: 1 }];
  };

  const cases = wb.addWorksheet("Cases");
  cases.columns = COLUMNS.map((c) => ({ header: c.header, width: c.width, style: FORMATS[c.kind] ? { numFmt: FORMATS[c.kind] } : {} }));
  for (const item of items) cases.addRow(COLUMNS.map((c) => c.get(item)));
  header(cases);
  cases.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: COLUMNS.length } };

  const summary = wb.addWorksheet("Summary");
  summary.columns = SUMMARY_HEADERS.map((h, i) => ({ header: h, width: i === 1 ? 32 : 16, style: i >= 4 ? { numFmt: "#,##0.00" } : {} }));
  for (const s of summarise(items)) summary.addRow(summaryCells(s));
  header(summary);

  return (await wb.xlsx.writeBuffer()) as ArrayBuffer;
}

export function fileName(now = new Date()): string {
  return `AR_confirmed_cases_${now.toISOString().slice(0, 10)}.xlsx`;
}

/** Builds the file and hands it to the browser as a download. */
export async function downloadWorkbook(items: ExportedCase[], name = fileName()): Promise<void> {
  const buffer = await buildWorkbook(items);
  const url = URL.createObjectURL(new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
