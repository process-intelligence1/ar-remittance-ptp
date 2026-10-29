import {
  type ActionRequest,
  type ActionResult,
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
  async performAction(_r: ActionRequest): Promise<ActionResult> {
    throw later("Actions");
  }
}
