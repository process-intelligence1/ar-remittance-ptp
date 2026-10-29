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
  UnauthorizedError,
  type WorkItemDetail,
  type WorkItemRow,
} from "./types";

export function toQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** The live edition: every call goes to the API. baseUrl is "" in local development (Vite proxy). */
export class LiveDataSource implements DataSource {
  readonly kind = "live" as const;
  private token: string | null = null;
  private unauthorizedHandler: () => void = () => {};

  constructor(private baseUrl: string = "") {}

  setToken(token: string | null) {
    this.token = token;
  }

  onUnauthorized(handler: () => void) {
    this.unauthorizedHandler = handler;
  }

  resolveUrl(url: string): string {
    return /^https?:/i.test(url) ? url : this.baseUrl + url;
  }

  private async request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body) headers.set("Content-Type", "application/json");
    if (auth && this.token) headers.set("Authorization", `Bearer ${this.token}`);
    const res = await fetch(this.baseUrl + path, { ...init, headers });
    if (res.status === 401 && auth) {
      this.unauthorizedHandler();
      throw new UnauthorizedError("Session expired - sign in again.");
    }
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* keep the status text */
      }
      throw new Error(detail);
    }
    return (await res.json()) as T;
  }

  async health(signal?: AbortSignal): Promise<boolean> {
    try {
      const res = await fetch(this.baseUrl + "/api/health", { signal, cache: "no-store" });
      return res.ok;
    } catch {
      return false;
    }
  }

  demoUsers(): Promise<DemoUser[]> {
    return this.request<DemoUser[]>("/api/auth/demo-users", {}, false);
  }

  login(user: string, accessCode: string): Promise<Session> {
    return this.request<Session>("/api/auth/demo-login", { method: "POST", body: JSON.stringify({ user, access_code: accessCode }) }, false);
  }

  workItems(params: ListParams): Promise<Page<WorkItemRow>> {
    return this.request(`/api/work-items${toQuery({ ...params })}`);
  }

  workItem(id: number | string): Promise<WorkItemDetail> {
    return this.request(`/api/work-items/${encodeURIComponent(String(id))}`);
  }

  kpis(filters: Filters): Promise<Kpis> {
    return this.request(`/api/kpis${toQuery({ ...filters })}`);
  }

  audit(params: Record<string, string | number | undefined>): Promise<Page<AuditRow>> {
    return this.request(`/api/audit${toQuery(params)}`);
  }

  changes(since: string): Promise<Changes> {
    return this.request(`/api/changes${toQuery({ since })}`);
  }

  attachmentLayout(id: number): Promise<AttachmentLayout> {
    return this.request(`/api/attachments/${id}/layout`);
  }

  async performAction(_request: ActionRequest): Promise<ActionResult> {
    // Actions (Confirm & Extract to Excel, Reject, ...) are built in M09.
    throw new NotAvailableError("This action is available in M09.");
  }
}
