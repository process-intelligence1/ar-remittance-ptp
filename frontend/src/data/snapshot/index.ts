import {
  NotAvailableError,
  type ActionOutcome,
  type ActionRequest,
  type AttachmentLayout,
  type AuditRow,
  type BsidChoice,
  type BulkOutcome,
  type BulkRequest,
  type Changes,
  type DataSource,
  type DemoDateResult,
  type DemoResetResult,
  type DemoSendResult,
  type DemoState,
  type DemoUser,
  type EmailPreview,
  type ExportedCase,
  type ExportedCases,
  type Filters,
  type Kpis,
  type ListParams,
  type Page,
  type PtpList,
  type PtpRunResult,
  type Session,
  type WorkerStart,
  type WorkItemDetail,
  type WorkItemRow,
} from "../types";
import { actionsFor, performBulk as bulkOf, performOne, type Ctx } from "./actions";
import { computeKpis } from "./kpis";
import { applyFilters, filterAudit, pageOf, sortRows, type SnapRow } from "./rows";
import { renderClarification } from "./templates";

export const DEMO_USERS: DemoUser[] = [
  { email: "analyst@acme-demo.local", name: "Asha (AR Analyst)", role: "AR_ANALYST" },
  { email: "cashapp@acme-demo.local", name: "Carlos (Cash Application)", role: "CASH_APPLICATION" },
  { email: "collections@acme-demo.local", name: "Chen (Collections Analyst)", role: "COLLECTIONS_ANALYST" },
  { email: "supervisor@acme-demo.local", name: "Sofia (AR Supervisor)", role: "AR_SUPERVISOR" },
];

interface Loaded {
  rows: SnapRow[];
  audit: AuditRow[];
  ptp: PtpList;
  meta: { business_date: string; generated_at: string };
}

const live = <T>(x: T): T => structuredClone(x);
const notHere = (what: string) => new NotAvailableError(`${what} is only in the live edition.`);

/**
 * The demo edition: no server. The data is static JSON (made by scripts.export_snapshot); everything else - filters, KPIs, the
 * analyst actions - is worked out here in the browser, so a change in the Action Queue shows on the Dashboard at once.
 * Changes live in memory only: a reload (or the Reset button) puts the loaded data back.
 */
export class SnapshotDataSource implements DataSource {
  readonly kind = "snapshot" as const;
  private user: DemoUser = DEMO_USERS[0];
  private data: Loaded | null = null;
  private pristine: Pick<Loaded, "rows" | "audit"> | null = null;
  private loading: Promise<Loaded> | null = null;
  private details = new Map<string, WorkItemDetail>();
  private extraAudit: AuditRow[] = [];
  private auditSeq = 0;

  constructor(private base: string = import.meta.env.BASE_URL ?? "/") {}

  // ---- plumbing
  private url(path: string) {
    return this.base.replace(/\/?$/, "/") + path;
  }
  private async json<T>(path: string): Promise<T> {
    const res = await fetch(this.url(path));
    if (!res.ok) throw new Error(`Could not load ${path} (${res.status})`);
    return (await res.json()) as T;
  }
  private load(): Promise<Loaded> {
    this.loading ??= (async () => {
      const [rows, audit, ptp, meta] = await Promise.all([
        this.json<SnapRow[]>("data/work_items.json"), this.json<AuditRow[]>("data/audit.json"),
        this.json<PtpList>("data/ptp.json"), this.json<Loaded["meta"]>("data/meta.json"),
      ]);
      this.pristine = { rows: live(rows), audit: live(audit) };
      this.auditSeq = Math.max(0, ...audit.map((a) => a.id));
      this.data = { rows, audit, ptp, meta };
      return this.data;
    })();
    return this.loading;
  }
  private ctx(d: Loaded): Ctx {
    return { user: this.user, businessDate: d.meta.business_date, nextAuditId: () => ++this.auditSeq, pushAudit: (a) => { d.audit.unshift(a); this.extraAudit.push(a); } };
  }
  private toRow = (r: SnapRow): WorkItemRow => {
    const { export: _export, exported_by: _by, ...row } = r;
    return { ...row, allowed_actions: actionsFor(this.user, r) } as WorkItemRow;
  };
  private find(d: Loaded, id: number | string): SnapRow {
    const r = d.rows.find((x) => (typeof id === "number" || /^\d+$/.test(String(id)) ? x.id === Number(id) : x.entry_id === String(id).toUpperCase()));
    if (!r) throw new Error(`Work item ${id} not found`);
    return r;
  }

  // ---- session (no server, no access code: the data is public synthetic data)
  setToken(token: string | null) {
    const email = token?.startsWith("snapshot:") ? token.slice(9) : null;
    this.user = DEMO_USERS.find((u) => u.email === email) ?? this.user;
  }
  onUnauthorized() {}
  resolveUrl(url: string) {
    return /^https?:|^data:|^blob:/i.test(url) ? url : this.url(url);
  }
  async health() {
    return true;
  }
  async demoUsers() {
    return DEMO_USERS;
  }
  async login(user: string): Promise<Session> {
    const u = DEMO_USERS.find((d) => d.email === user) ?? DEMO_USERS[0];
    this.user = u;
    return { token: `snapshot:${u.email}`, expires_at: new Date(Date.now() + 12 * 3600e3).toISOString(), user: u };
  }

  // ---- Action Queue, Record Detail, Dashboard, Audit
  async workItems(p: ListParams): Promise<Page<WorkItemRow>> {
    const d = await this.load();
    const inScope = p.in_scope ? d.rows.filter((r) => r.classification !== "OUT_OF_SCOPE") : d.rows; // the Action Queue leaves out-of-scope e-mails out (as the API does)
    const rows = sortRows(applyFilters(inScope, p as Filters), p.sort, p.order);
    const page = pageOf(rows, p.page ?? 1, p.page_size ?? 50);
    return { ...page, items: page.items.map(this.toRow) };
  }

  async workItem(id: number | string): Promise<WorkItemDetail> {
    const d = await this.load();
    const r = this.find(d, id);
    let base = this.details.get(r.entry_id);
    if (!base) {
      base = await this.json<WorkItemDetail>(`data/details/${r.entry_id}.json`);
      this.details.set(r.entry_id, base);
    }
    const mine = this.extraAudit.filter((a) => a.entity_id === r.entry_id).sort((a, b) => a.id - b.id);
    const { export: _e, exported_by: _b, ...fields } = r;
    return {
      ...base, ...fields, allowed_actions: actionsFor(this.user, r), work_item: { ...base.work_item, status: r.status },
      attachments: base.attachments.map((a) => {
        const x = a as typeof a & { file?: string; file_kind?: string; pages_url?: string | null };
        return { ...a, url: x.file_kind === "sample" ? `samples/${x.file}` : (x.file ?? a.url), page_url: x.pages_url ?? undefined };
      }),
      audit: [...base.audit, ...mine],
    } as WorkItemDetail;
  }

  async kpis(filters: Filters): Promise<Kpis> {
    return computeKpis((await this.load()).rows, filters);
  }

  async audit(params: Record<string, string | number | undefined>): Promise<Page<AuditRow>> {
    const d = await this.load();
    return pageOf(filterAudit(d.audit, params), Number(params.page ?? 1), Number(params.page_size ?? 50));
  }

  async changes(_since: string): Promise<Changes> {
    return { server_time: new Date().toISOString(), next_since: new Date().toISOString(), new_work_items: { count: 0, ids: [] }, updated_work_items: { count: 0, ids: [] }, new_emails: 0, changed: false };
  }

  async attachmentLayout(id: number): Promise<AttachmentLayout> {
    const t = await this.json<{ id: number; filename: string; text: string | null }>(`data/texts/${id}.json`).catch(() => ({ id, filename: "", text: null }));
    return { id, filename: t.filename, page_count: null, parse_method: null, text: t.text, layout: null };
  }

  // ---- analyst actions (in memory)
  async performAction(id: number | string, req: ActionRequest): Promise<ActionOutcome> {
    const d = await this.load();
    return performOne(this.ctx(d), this.find(d, id), req, this.toRow);
  }
  async performBulk(req: BulkRequest): Promise<BulkOutcome> {
    const d = await this.load();
    return bulkOf(this.ctx(d), req.items.map((i) => this.find(d, i.id)), req, this.toRow);
  }
  async previewEmail(id: number | string, question?: string): Promise<EmailPreview> {
    return renderClarification(this.find(await this.load(), id), question);
  }
  async bsidChoices(_id: number | string, _q?: string): Promise<BsidChoice[]> {
    throw notHere("Choosing a BSID item (it needs the matching engine)");
  }

  // ---- Exported cases: every confirmed row, as the live system lists them
  async exportedCases(): Promise<ExportedCases> {
    const d = await this.load();
    const items: ExportedCase[] = d.rows.filter((r) => r.status === "CONFIRMED")
      .sort((a, b) => (a.confirmed_at ?? "").localeCompare(b.confirmed_at ?? "") || a.id - b.id)
      .map((r) => {
        const x = r.export, inv = x.bsid_amount, sameCurrency = !r.currency || r.currency === x.bsid_currency;
        return {
          entry_id: r.entry_id, email_ref: r.email_ref, received_at: r.received_at, sender_email: r.sender_email, kunnr: r.kunnr?.replace(/^0+/, "") ?? null,
          customer_name: r.customer_name, company_code: r.company_code, invoice_ref: r.invoice_ref, belnr: x.belnr, gjahr: x.gjahr, buzei: x.buzei,
          invoice_amount: inv, invoice_currency: x.bsid_currency, paid_amount: r.amount, paid_currency: r.currency ?? x.bsid_currency,
          difference: r.amount !== null && inv !== null && sameCurrency ? Math.round((r.amount - inv) * 1000) / 1000 : null,
          payment_date: x.payment_date, payment_reference: x.payment_reference, match_level: r.match_level, confidence: r.confidence, decision: r.decision,
          confirmed_by: r.confirmed_by ?? null, confirmed_at: r.confirmed_at ?? null, comment: r.action_comment ?? null,
          exported_at: r.exported_at ?? null, exported_by: r.exported_by ?? null,
        };
      });
    return { count: items.length, items };
  }
  async markExported(entryIds?: string[]): Promise<number> {
    const d = await this.load();
    const now = new Date().toISOString();
    let n = 0;
    for (const r of d.rows.filter((x) => x.status === "CONFIRMED" && (!entryIds || entryIds.includes(x.entry_id)))) {
      r.exported_at = now;
      r.exported_by = this.user.email;
      this.ctx(d).pushAudit({ id: ++this.auditSeq, occurred_at: now, business_date: d.meta.business_date, actor: this.user.email, actor_role: this.user.role,
        entity_type: "work_item", entity_id: r.entry_id, action: "EXPORTED_TO_EXCEL", details: { after: { exported_at: now, exported_by: this.user.email } } });
      n += 1;
    }
    return n;
  }

  // ---- PTP Tracker (as exported; the daily check needs the server)
  async ptpList(p: { status?: string; q?: string; customer?: string; page?: number; page_size?: number }): Promise<PtpList> {
    const d = await this.load();
    const q = p.q?.toLowerCase(), cust = p.customer?.toLowerCase();
    const items = d.ptp.items.filter((x) => (!p.status || x.status === p.status.toUpperCase())
      && (!q || [x.entry_id, x.invoice_ref, x.customer_name].some((v) => (v ?? "").toLowerCase().includes(q)))
      && (!cust || (x.customer_name ?? "").toLowerCase().includes(cust) || x.kunnr === p.customer));
    const page = pageOf(items, p.page ?? 1, p.page_size ?? 100);
    return { ...d.ptp, ...page, counts: d.ptp.counts };
  }
  async runPtpChecks(): Promise<PtpRunResult> {
    throw notHere("The promise check");
  }

  // ---- Demo Control belongs to the live edition
  async demoState(): Promise<DemoState> {
    throw notHere("Demo Control");
  }
  async demoSendSample(_c: string, _p: boolean): Promise<DemoSendResult> {
    throw notHere("Sending a sample e-mail");
  }
  async demoProcessNow(): Promise<WorkerStart> {
    throw notHere("Process now");
  }
  async demoSetBusinessDate(_c: { date: string } | { add_days: number }): Promise<DemoDateResult> {
    throw notHere("Moving the business date");
  }
  async demoReset(): Promise<DemoResetResult> {
    throw notHere("Reset demo");
  }

  /** The Reset button of the demo edition: everything loaded is put back. */
  resetSnapshot(): void {
    if (!this.data || !this.pristine) return;
    this.data.rows = live(this.pristine.rows);
    this.data.audit = live(this.pristine.audit);
    this.extraAudit = [];
    this.auditSeq = Math.max(0, ...this.data.audit.map((a) => a.id));
  }
}
