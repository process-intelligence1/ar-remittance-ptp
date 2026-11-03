import { render } from "@testing-library/react";
import App from "../App";
import type { DataSource, DemoUser, Kpis, Page, Session, WorkItemDetail, WorkItemRow } from "../data";

export const USERS: DemoUser[] = [
  { email: "analyst@acme-demo.local", name: "Asha (AR Analyst)", role: "AR_ANALYST" },
  { email: "cashapp@acme-demo.local", name: "Carlos (Cash Application)", role: "CASH_APPLICATION" },
];

export function row(over: Partial<WorkItemRow> = {}): WorkItemRow {
  return {
    id: 1, entry_id: "ENT-000001", email_ref: "EML-000001", received_at: "2026-10-12T09:00:00Z", sender_email: "ap@x.example",
    subject: "Remittance", customer_name: "Innova Care", kunnr: "0000100001", company_code: "1000", region: "EMEA",
    classification: "REMITTANCE", line_type: "REMITTANCE", invoice_ref: "INV-1", match_field: "XBLNR", match_level: "EXACT",
    bsid_match: true, amount: 100, currency: "USD", amount_usd: 100, usd_status: "OK", confidence: 95.3,
    confidence_source: "FORMULA", decision: "AUTO_PROCESS", status: "AUTO_PROCESSED", exception_reason: null,
    review_reasons: null, recommended_action: "Confirm & Add to Excel", assigned_role: "CASH_APPLICATION", sla_due_at: null,
    duplicate_of: null, updated_at: "2026-10-12T09:00:00Z", version: 1, allowed_actions: ["CONFIRM_ADD_EXCEL"], ...over,
  };
}

export const KPIS: Kpis = {
  cards: { total: { count: 3, usd: 300 }, ai: { count: 1, usd: 100 }, manual: { count: 1, usd: 100 }, duplicates: { count: 0, usd: 0 }, exceptions: { count: 1, usd: 100 } },
  usd: { unconverted: 0, missing_rate_currencies: {}, note: "" },
  distributions: { customer: [{ label: "Innova Care", count: 3, usd: 300 }], region: [{ label: "EMEA", count: 3, usd: 300 }], company_code: [], classification: [], status: [] },
  charts: {
    performance: [{ label: "Remittance", auto: 1, manual: 1, exceptions: 1, total: 3 }, { label: "Promise-to-Pay", auto: 0, manual: 0, exceptions: 0, total: 0 }],
    dimensions: { customer: [{ label: "Innova Care", auto: 1, manual: 1, duplicates: 0, exceptions: 1, total: 3 }], region: [], company_code: [] },
    trend: { date: [], week: [], month: [{ key: "2026-10", label: "Oct 2026", remittance: { total: 3, auto: 1 }, ptp: { total: 0, auto: 0 } }], quarter: [] },
  },
  monthly_trend: [], performance_stability: [],
};

export function fakeDs(over: Partial<DataSource> & { rows?: WorkItemRow[] } = {}): DataSource {
  const rows = over.rows ?? [row()];
  const page = (): Page<WorkItemRow> => ({ total: rows.length, page: 1, page_size: 25, items: rows });
  const ds: DataSource = {
    kind: "live",
    health: async () => true,
    demoUsers: async () => USERS,
    login: async (user: string): Promise<Session> => ({ token: "t", expires_at: new Date(Date.now() + 3600e3).toISOString(), user: USERS.find((u) => u.email === user)! }),
    setToken: () => {},
    onUnauthorized: () => {},
    workItems: async () => page(),
    workItem: async () => { throw new Error("not used"); },
    kpis: async () => KPIS,
    audit: async () => ({ total: 0, page: 1, page_size: 50, items: [] }),
    changes: async () => ({ server_time: "", next_since: "2026-01-01T00:00:00Z", new_work_items: { count: 0, ids: [] }, updated_work_items: { count: 0, ids: [] }, new_emails: 0, changed: false }),
    attachmentLayout: async () => ({ id: 1, filename: "a", page_count: 1, parse_method: "text", text: "", layout: null }),
    resolveUrl: (u: string) => u,
    performAction: async (_id, r) => ({ item: row({ version: r.version + 1, status: "CONFIRMED", allowed_actions: [] }), outbound_id: null, worker_started: null }),
    performBulk: async (r) => ({ done: r.items.length, items: [] }),
    previewEmail: async () => ({ subject: "[AR-DEMO][CLARIFICATION → ap@x.example] Clarification needed", body: "Dear Innova Care, please confirm.", language: "en", intended_recipient: "ap@x.example", actual_recipient: "demo@mailbox.example", template: "clarification_en" }),
    bsidChoices: async () => [{ id: 7, bukrs: "1000", kunnr: "0000100001", customer_name: "Innova Care", belnr: "9002600125", gjahr: "2026", buzei: "001", xblnr: "INV-1", amount: 100, waers: "USD", bldat: "2026-09-01", source: "customer", selected: false }],
    exportedCases: async () => ({ count: 0, items: [] }),
    markExported: async () => 0,
    ptpList: async () => ({ business_date: "2026-10-28", grace_days: 3, total: 0, page: 1, page_size: 100, counts: { OPEN: 0, PARTIALLY_KEPT: 0, KEPT: 0, BROKEN: 0, ESCALATED: 0, CANCELLED: 0 }, items: [] }),
    demoState: async () => ({ business_date: "2026-10-28", default_business_date: "2026-10-28", reset_point: null, live_set: [], live_set_error: null, sent_total: 0 }),
    demoSendSample: async (code: string) => ({ code, gmail_id: "g1", from: "ap@x.example", subject: "Remittance advice", worker: { started: true } }),
    demoProcessNow: async () => ({ started: true }),
    demoSetBusinessDate: async () => ({ business_date: "2026-11-27", before: "2026-10-28", ptp: { checked: 0, changed: [], alerts: 0, escalations: 0 }, worker: null }),
    demoReset: async () => ({ reset_point_taken_at: "2026-10-28T10:00:00Z", business_date: "2026-10-28", restored_rows: { work_item: 3 }, sap_restored: false }),
    runPtpChecks: async () => ({ business_date: "2026-10-28", checked: 0, changed: [], alerts: 0, escalations: 0, counts: {} }),
  };
  const { rows: _ignored, ...rest } = over;
  return { ...ds, ...rest };
}

export function signedIn(user: DemoUser = USERS[0]) {
  sessionStorage.setItem("ar_session", JSON.stringify({ token: "t", expires_at: new Date(Date.now() + 3600e3).toISOString(), user }));
}

export function renderApp(ds: DataSource, hash: string) {
  window.location.hash = hash;
  return render(<App dataSource={ds} />);
}

/** A full record detail for the pop-up tests. */
export function detail(over: Partial<WorkItemDetail> = {}): WorkItemDetail {
  const base = row();
  return {
    ...base,
    work_item: { payment_date: "2026-10-12", remittance_ref: "PAY-1", promise_date: null, deduction_amount: null },
    email: { sender_name: "AP Team", body_text_clean: "Dear AR, payment attached.", body_text: "Dear AR, payment attached." },
    attachments: [],
    classification_detail: null, extraction: null, extraction_line: null, evidence: null,
    candidates: [{ rank: 1, chosen: true, confidence_score: 95.3, scores: { level: "EXACT" }, bsid_item: { belnr: "9002600125", xblnr: "INV-1", wrbtr: 100, waers: "USD" } }],
    score_breakdown: {
      invoice_match_score: 1, amount_alignment_score: 1, sender_company_score: 1, customer_name_similarity: 0.957, date_proxy_score: 0.6,
      raw_score: 0.858, confidence_score: 95.3, confidence_category: "HIGH", confidence_source: "FORMULA", formula_confidence: 95.3,
      fast_path_override: "EXACT_FULL_MATCH", amount_difference_pct: 0.241, date_difference_days: 144, payer_cluster_flag: null, currency_cluster_flag: null,
    },
    bsid: { matched: true, invoice: "INV-1", document: "9002600125", fiscal_year: "2026", item: "001", customer_no: "0000100001", customer_name: "Innova Care Products",
      company_code: "1000", amount: 100, currency: "USD", posting_date: "2026-09-01", debit_credit: "S", open_item_status: "OPEN", amount_difference_pct: 0.241 },
    ptp_commitments: [], same_email_items: [], audit: [],
    ...over,
  };
}
