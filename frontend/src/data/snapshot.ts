import {
  type ActionOutcome,
  type ActionRequest,
  type BsidChoice,
  type BulkOutcome,
  type BulkRequest,
  type EmailPreview,
  type PtpList,
  type PtpRunResult,
  type ExportedCases,
  type AttachmentLayout,
  type AuditRow,
  type Changes,
  type DataSource,
  type DemoUser,
  type Filters,
  type Kpis,
  type ListParams,
  NotAvailableError,
  type Page,
  type Session,
  type WorkItemDetail,
  type WorkItemRow,
} from "./types";

const DEMO_USERS: DemoUser[] = [
  { email: "analyst@acme-demo.local", name: "Asha (AR Analyst)", role: "AR_ANALYST" },
  { email: "cashapp@acme-demo.local", name: "Carlos (Cash Application)", role: "CASH_APPLICATION" },
  { email: "collections@acme-demo.local", name: "Chen (Collections Analyst)", role: "COLLECTIONS_ANALYST" },
  { email: "supervisor@acme-demo.local", name: "Sofia (AR Supervisor)", role: "AR_SUPERVISOR" },
];

const later = (what: string) => new NotAvailableError(`${what}: the demo edition (static snapshot) arrives in M15.`);

/** The demo edition: static JSON, no server. Placeholder until M15 - same contract as the live edition. */
export class SnapshotDataSource implements DataSource {
  readonly kind = "snapshot" as const;

  setToken() {}
  onUnauthorized() {}
  resolveUrl(url: string) {
    return url;
  }
  async health() {
    return true;
  }
  async demoUsers() {
    return DEMO_USERS;
  }
  async login(user: string): Promise<Session> {
    const u = DEMO_USERS.find((d) => d.email === user) ?? DEMO_USERS[0];
    return { token: "snapshot", expires_at: new Date(Date.now() + 12 * 3600e3).toISOString(), user: u };
  }
  async workItems(_p: ListParams): Promise<Page<WorkItemRow>> {
    throw later("Work items");
  }
  async workItem(_id: number | string): Promise<WorkItemDetail> {
    throw later("Record detail");
  }
  async kpis(_f: Filters): Promise<Kpis> {
    throw later("Dashboard");
  }
  async audit(_p: Record<string, string | number | undefined>): Promise<Page<AuditRow>> {
    throw later("Audit trail");
  }
  async changes(_since: string): Promise<Changes> {
    throw later("Changes");
  }
  async attachmentLayout(_id: number): Promise<AttachmentLayout> {
    throw later("Attachment layout");
  }
  async performAction(_id: number | string, _r: ActionRequest): Promise<ActionOutcome> {
    throw later("Actions");
  }
  async performBulk(_r: BulkRequest): Promise<BulkOutcome> {
    throw later("Bulk actions");
  }
  async previewEmail(_id: number | string, _q?: string): Promise<EmailPreview> {
    throw later("E-mail preview");
  }
  async bsidChoices(_id: number | string, _q?: string): Promise<BsidChoice[]> {
    throw later("BSID items");
  }
  async exportedCases(): Promise<ExportedCases> {
    throw later("Exported cases");
  }
  async markExported(_ids?: string[]): Promise<number> {
    throw later("Exported cases");
  }
  async ptpList(_p: { status?: string; q?: string; customer?: string; page?: number; page_size?: number }): Promise<PtpList> {
    throw later("PTP Tracker");
  }
  async runPtpChecks(): Promise<PtpRunResult> {
    throw later("PTP check");
  }
}
