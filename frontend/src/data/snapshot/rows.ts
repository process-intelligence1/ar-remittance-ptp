import type { AuditRow, Filters, WorkItemRow } from "../types";

// Row-level logic of the demo edition: the same filters and sort orders as backend/app/api/workitems.py (apply_filters, SORTS)
// and the Audit Trail endpoint, applied to the rows loaded from the snapshot.

/** What the snapshot adds to a Queue row beyond the live API (used for KPIs, the Excel export and the e-mail preview). */
export interface RowExport {
  payment_date: string | null;
  payment_reference: string | null;
  belnr: string | null;
  gjahr: string | null;
  buzei: string | null;
  bsid_amount: number | null;
  bsid_currency: string | null;
  language: string;
  source: string;
  email_business_date: string | null;
  invoice_ref_norm?: string | null;
}

export type SnapRow = Omit<WorkItemRow, "allowed_actions"> & {
  resolved: boolean;
  export: RowExport;
  exported_by?: string | null;
};

/** The calendar date of a timestamp as written in the string (the server writes it in its own time zone, as its SQL does). */
export const dayOf = (iso: string | null | undefined): string | null => (iso ? iso.slice(0, 10) : null);

export function applyFilters(rows: SnapRow[], f: Filters): SnapRow[] {
  const lc = (s: string | null | undefined) => (s ?? "").toLowerCase();
  const q = f.q?.trim().toLowerCase();
  const cust = f.customer?.trim();
  return rows.filter((r) => {
    const day = dayOf(r.received_at);
    if (f.from_date && !(day && day >= f.from_date)) return false;
    if (f.to_date && !(day && day <= f.to_date)) return false;
    if (f.classification && r.classification !== f.classification.toUpperCase()) return false;
    if (f.bsid_match !== undefined && r.bsid_match !== (f.bsid_match === "true")) return false;
    if (f.status && r.status !== f.status.toUpperCase()) return false;
    if (f.decision && r.decision !== f.decision.toUpperCase()) return false;
    if (f.min_confidence !== undefined && !(r.confidence !== null && r.confidence >= f.min_confidence)) return false;
    if (f.max_confidence !== undefined && !(r.confidence !== null && r.confidence <= f.max_confidence)) return false;
    if (cust && !(r.kunnr === cust.padStart(10, "0") || r.kunnr === cust || lc(r.customer_name).includes(cust.toLowerCase()))) return false;
    if (f.company_code && r.company_code !== f.company_code) return false;
    if (f.region && r.region !== f.region) return false;
    if (q && ![r.entry_id, r.email_ref, r.invoice_ref, r.export.invoice_ref_norm, r.customer_name, r.sender_email, r.subject].some((v) => lc(v).includes(q))) return false;
    return true;
  });
}

const SORT_KEYS: Record<string, (r: SnapRow) => string | number | null> = {
  received_at: (r) => r.received_at, entry_id: (r) => r.entry_id, confidence: (r) => r.confidence, amount: (r) => r.amount,
  customer: (r) => r.customer_name, status: (r) => r.status, decision: (r) => r.decision, sla_due_at: (r) => r.sla_due_at,
  company_code: (r) => r.company_code, classification: (r) => r.classification, updated_at: (r) => r.updated_at,
};

/** Sorted like the API: empty values last whichever way you sort, ties by id, newest first. */
export function sortRows(rows: SnapRow[], sort = "received_at", order: "asc" | "desc" = "desc"): SnapRow[] {
  const key = SORT_KEYS[sort] ?? SORT_KEYS.received_at;
  const dir = order === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = key(a), y = key(b);
    if (x === null && y !== null) return 1;
    if (y === null && x !== null) return -1;
    if (x !== null && y !== null && x !== y) return (x < y ? -1 : 1) * dir;
    return b.id - a.id;
  });
}

export function pageOf<T>(items: T[], page = 1, pageSize = 50): { total: number; page: number; page_size: number; items: T[] } {
  return { total: items.length, page, page_size: pageSize, items: items.slice((page - 1) * pageSize, page * pageSize) };
}

export function filterAudit(rows: AuditRow[], p: Record<string, string | number | undefined>): AuditRow[] {
  const has = (v: string | null | undefined, needle: unknown) => (v ?? "").toLowerCase().includes(String(needle).toLowerCase());
  const out = rows.filter((a) => {
    const day = dayOf(a.occurred_at);
    if (p.from_date && !(day && day >= String(p.from_date))) return false;
    if (p.to_date && !(day && day <= String(p.to_date))) return false;
    if (p.actor && !has(a.actor, p.actor)) return false;
    if (p.action && a.action !== String(p.action).toUpperCase()) return false;
    if (p.entity_type && a.entity_type !== p.entity_type) return false;
    if (p.entity_id && a.entity_id !== p.entity_id) return false;
    if (p.q && !(has(a.entity_id, p.q) || has(a.action, p.q) || has(a.actor, p.q))) return false;
    return true;
  });
  return out.sort((a, b) => (a.occurred_at === b.occurred_at ? b.id - a.id : a.occurred_at < b.occurred_at ? 1 : -1));
}
