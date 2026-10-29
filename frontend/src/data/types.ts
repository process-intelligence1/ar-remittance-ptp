// The one contract between the screens and the data. Screens only talk to a DataSource (see ./index.ts):
// "live" = the API, "snapshot" = static JSON (M15). Screens never call fetch directly; actions go through it too.

export type Role = "AR_ANALYST" | "CASH_APPLICATION" | "COLLECTIONS_ANALYST" | "AR_SUPERVISOR";

export interface DemoUser {
  email: string;
  name: string;
  role: Role;
}

export interface Session {
  token: string;
  expires_at: string;
  user: DemoUser;
}

export type ActionCode =
  | "CONFIRM_EXTRACT_EXCEL"
  | "ADD_UPDATE_DETAILS"
  | "ADD_BSID_DETAILS"
  | "REJECT"
  | "REQUEST_CLARIFICATION"
  | "ESCALATE_TO_SUPERVISOR"
  | "CLOSE_AS_DUPLICATE"
  | "MARK_NON_DUPLICATE";

export interface Filters {
  from_date?: string;
  to_date?: string;
  classification?: string;
  bsid_match?: "true" | "false";
  status?: string;
  decision?: string;
  min_confidence?: number;
  max_confidence?: number;
  customer?: string;
  company_code?: string;
  region?: string;
  q?: string;
}

export interface ListParams extends Filters {
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface Page<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface WorkItemRow {
  id: number;
  entry_id: string;
  email_ref: string;
  received_at: string | null;
  sender_email: string | null;
  subject: string | null;
  customer_name: string | null;
  kunnr: string | null;
  company_code: string | null;
  region: string | null;
  classification: string;
  line_type: string | null;
  invoice_ref: string | null;
  match_field: string | null;
  match_level: string | null;
  bsid_match: boolean;
  amount: number | null;
  currency: string | null;
  amount_usd: number | null;
  usd_status: "OK" | "NO_RATE" | "NO_AMOUNT";
  confidence: number | null;
  confidence_source: string | null;
  decision: string | null;
  status: string;
  exception_reason: string | null;
  review_reasons: string[] | null;
  recommended_action: string | null;
  assigned_role: string | null;
  sla_due_at: string | null;
  duplicate_of: string | null;
  updated_at: string;
  allowed_actions: ActionCode[];
}

export interface Attachment {
  id: number;
  parent_id: number | null;
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  page_count: number | null;
  parse_method: string | null;
  url: string; // signed, short-lived download link
  page_url?: string; // signed link template for page images; "{page}" is replaced
  viewable_inline: boolean;
}

export interface EvidenceBox {
  attachmentId: number;
  page: number;
  bbox: [number, number, number, number]; // fractions of the page: x0, y0, x1, y1
  label: string;
  text: string;
}

export interface Candidate {
  rank: number;
  chosen: boolean;
  confidence_score: number | null;
  scores: Record<string, unknown>;
  bsid_item: Record<string, unknown> | null;
}

export interface AuditRow {
  id: number;
  occurred_at: string;
  business_date: string | null;
  actor: string;
  actor_role: string | null;
  entity_type: string;
  entity_id: string | null;
  action: string;
  details: Record<string, unknown> | null;
}

export interface WorkItemDetail extends WorkItemRow {
  work_item: Record<string, unknown>;
  email: Record<string, unknown> & { body_text?: string; body_text_clean?: string; sender_name?: string };
  attachments: Attachment[];
  classification_detail: Record<string, unknown> | null;
  extraction: Record<string, unknown> | null;
  extraction_line: Record<string, unknown> | null;
  evidence: unknown;
  candidates: Candidate[];
  score_breakdown: Record<string, number | string | boolean | null>;
  ptp_commitments: Record<string, unknown>[];
  same_email_items: WorkItemRow[];
  audit: AuditRow[];
}

export interface DistributionPoint {
  label: string;
  count: number;
  usd: number | null;
}

export interface Kpis {
  cards: Record<"total" | "ai" | "manual" | "duplicates" | "exceptions", { count: number; usd: number | null }>;
  usd: { unconverted: number; missing_rate_currencies: Record<string, number>; note: string };
  distributions: Record<"customer" | "region" | "company_code" | "classification" | "status", DistributionPoint[]>;
  monthly_trend: { month: string; total: number; ai: number; manual: number; duplicates: number; exceptions: number }[];
  performance_stability: { date: string; rows: number; auto_rate: number | null; avg_confidence: number | null }[];
}

export interface Changes {
  server_time: string;
  next_since: string;
  new_work_items: { count: number; ids: number[] };
  updated_work_items: { count: number; ids: number[] };
  new_emails: number;
  changed: boolean;
}

export interface AttachmentLayout {
  id: number;
  filename: string;
  page_count: number | null;
  parse_method: string | null;
  text: string | null;
  layout: unknown;
}

export interface ActionRequest {
  action: ActionCode;
  ids: number[];
  comment?: string;
  payload?: Record<string, unknown>;
}

export interface ActionResult {
  ok: boolean;
  message: string;
}

export class NotAvailableError extends Error {}
export class UnauthorizedError extends Error {}

export interface DataSource {
  readonly kind: "live" | "snapshot";
  /** true when the server answers (also wakes it up after idle) */
  health(signal?: AbortSignal): Promise<boolean>;
  demoUsers(): Promise<DemoUser[]>;
  login(user: string, accessCode: string): Promise<Session>;
  setToken(token: string | null): void;
  onUnauthorized(handler: () => void): void;
  workItems(params: ListParams): Promise<Page<WorkItemRow>>;
  workItem(id: number | string): Promise<WorkItemDetail>;
  kpis(filters: Filters): Promise<Kpis>;
  audit(params: Record<string, string | number | undefined>): Promise<Page<AuditRow>>;
  changes(since: string): Promise<Changes>;
  attachmentLayout(id: number): Promise<AttachmentLayout>;
  /** turns a (possibly relative) signed link from the API into a URL the browser can load */
  resolveUrl(url: string): string;
  /** actions of the Action Queue / Record Detail (built in M09) */
  performAction(request: ActionRequest): Promise<ActionResult>;
}
