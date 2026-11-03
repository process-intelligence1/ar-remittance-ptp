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
  | "CONFIRM_ADD_EXCEL"
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
  /** the Action Queue: leave out-of-scope e-mails out (they stay in the audit trail) */
  in_scope?: boolean;
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
  promise_date?: string | null; // a payment plan (instalments) makes one row per instalment for the same invoice
  line_no?: number;
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
  /** row version: every action must send the version the user saw (a stale one is refused with 409) */
  version: number;
  action_comment?: string | null;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  exported_at?: string | null;
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

/** The matched SAP open item (BSID) with its customer - the "SAP BSID Match" block of the record detail. */
export interface BsidMatch {
  matched: boolean;
  invoice?: string | null;
  document?: string;
  fiscal_year?: string;
  item?: string;
  customer_no?: string;
  customer_name?: string | null;
  company_code?: string;
  amount?: number;
  currency?: string;
  posting_date?: string | null;
  debit_credit?: string;
  open_item_status?: string | null;
  amount_difference_pct?: number | null;
  /** open BSID items that carry the same invoice number (candidates); more than one = the best match was chosen by amount and currency */
  shared_invoice_count?: number;
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
  bsid?: BsidMatch; // missing when the API is an older version
  ptp_commitments: Record<string, unknown>[];
  same_email_items: WorkItemRow[];
  audit: AuditRow[];
}

export interface DistributionPoint {
  label: string;
  count: number;
  usd: number | null;
}

export interface PerformancePoint {
  label: string;
  auto: number;
  manual: number;
  exceptions: number;
  total: number;
}

export interface DimensionPoint {
  label: string;
  auto: number;
  manual: number;
  duplicates: number;
  exceptions: number;
  total: number;
}

export type ChartDimension = "customer" | "region" | "company_code";
export type TrendPeriod = "date" | "week" | "month" | "quarter";

export interface TrendPoint {
  key: string;
  label: string;
  remittance: { total: number; auto: number };
  ptp: { total: number; auto: number };
}

/** The three Dashboard charts. Same shape from the API (live) and from data/charts.ts (demo edition). */
export interface ChartsData {
  performance: PerformancePoint[];
  dimensions: Record<ChartDimension, DimensionPoint[]>;
  trend: Record<TrendPeriod, TrendPoint[]>;
}

export interface Kpis {
  cards: Record<"total" | "ai" | "manual" | "duplicates" | "exceptions", { count: number; usd: number | null }>;
  usd: { unconverted: number; missing_rate_currencies: Record<string, number>; note: string };
  distributions: Record<"customer" | "region" | "company_code" | "classification" | "status", DistributionPoint[]>;
  charts?: ChartsData; // missing when the API is an older version
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

/** One action on one record (Add / Update details sends `details`, Request Clarification sends `email`). */
export interface ActionRequest {
  action: ActionCode;
  version: number;
  comment?: string;
  details?: DetailsInput;
  email?: { subject: string; body: string };
}

/** The fields an analyst may change in "Add / Update Invoice Details" (any of them), and the BSID item picked by hand. */
export interface DetailsInput {
  invoice_ref?: string;
  amount?: string;
  currency?: string;
  payment_date?: string;
  payment_reference?: string;
  kunnr?: string;
  bukrs?: string;
  bsid_id?: number;
}

export interface ActionOutcome {
  item: WorkItemRow;
  outbound_id: number | null;
  /** true when the e-mail job was started at once; false = it is sent by the next scheduled run; null = no e-mail */
  worker_started: boolean | null;
}

export interface BulkRequest {
  action: ActionCode;
  comment?: string;
  items: { id: number | string; version: number }[];
}

export interface BulkOutcome {
  done: number;
  items: WorkItemRow[];
}

export interface EmailPreview {
  subject: string;
  body: string;
  language: string;
  intended_recipient: string;
  actual_recipient: string;
  template: string;
}

/** An open BSID item the analyst can pick in the details dialog. */
export interface BsidChoice {
  id: number;
  bukrs: string;
  kunnr: string;
  customer_name: string | null;
  belnr: string;
  gjahr: string;
  buzei: string;
  xblnr: string | null;
  amount: number;
  waers: string;
  bldat: string | null;
  source: "candidate" | "customer" | "search";
  selected: boolean;
}

/** One confirmed case = one row of the "Exported cases" Excel view and of the downloaded file. */
export interface ExportedCase {
  entry_id: string;
  email_ref: string;
  received_at: string | null;
  sender_email: string | null;
  kunnr: string | null;
  customer_name: string | null;
  company_code: string | null;
  invoice_ref: string | null;
  belnr: string | null;
  gjahr: string | null;
  buzei: string | null;
  invoice_amount: number | null;
  invoice_currency: string | null;
  paid_amount: number | null;
  paid_currency: string | null;
  difference: number | null;
  payment_date: string | null;
  payment_reference: string | null;
  match_level: string | null;
  confidence: number | null;
  decision: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
  comment: string | null;
  exported_at: string | null;
  exported_by: string | null;
}

export interface ExportedCases {
  count: number;
  items: ExportedCase[];
}

/** The server refused an action: `status` 409 = changed by someone else, 403 = not allowed, 422 = not valid. */
export class ActionError extends Error {
  constructor(message: string, public status: number, public problems: { entry_id: string; message: string }[] = []) {
    super(message);
  }
}

export class NotAvailableError extends Error {}
export class UnauthorizedError extends Error {}
/** The server could not be reached at all (restarting, offline) - not an answer such as 401 or 500. */
export class NetworkError extends Error {}

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
  /** actions of the Action Queue / Record Detail (M09); all of them go through here, in both editions */
  performAction(id: number | string, request: ActionRequest): Promise<ActionOutcome>;
  /** one action on several records - all or nothing */
  performBulk(request: BulkRequest): Promise<BulkOutcome>;
  previewEmail(id: number | string, question?: string): Promise<EmailPreview>;
  bsidChoices(id: number | string, q?: string): Promise<BsidChoice[]>;
  /** ALL confirmed cases (the Excel view and the file) */
  exportedCases(): Promise<ExportedCases>;
  /** records exported_at / exported_by for the downloaded cases */
  markExported(entryIds?: string[]): Promise<number>;
}
