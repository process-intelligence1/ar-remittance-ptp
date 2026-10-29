import { render } from "@testing-library/react";
import App from "../App";
import type { ActionRequest, ActionResult, DataSource, DemoUser, Kpis, Page, Session, WorkItemRow } from "../data";
import { NotAvailableError } from "../data";

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
    review_reasons: null, recommended_action: "Confirm & Extract to Excel", assigned_role: "CASH_APPLICATION", sla_due_at: null,
    duplicate_of: null, updated_at: "2026-10-12T09:00:00Z", allowed_actions: ["CONFIRM_EXTRACT_EXCEL"], ...over,
  };
}

export const KPIS: Kpis = {
  cards: { total: { count: 3, usd: 300 }, ai: { count: 1, usd: 100 }, manual: { count: 1, usd: 100 }, duplicates: { count: 0, usd: 0 }, exceptions: { count: 1, usd: 100 } },
  usd: { unconverted: 0, missing_rate_currencies: {}, note: "" },
  distributions: { customer: [{ label: "Innova Care", count: 3, usd: 300 }], region: [{ label: "EMEA", count: 3, usd: 300 }], company_code: [], classification: [], status: [] },
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
    performAction: async (_r: ActionRequest): Promise<ActionResult> => { throw new NotAvailableError("This action is available in M09."); },
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
