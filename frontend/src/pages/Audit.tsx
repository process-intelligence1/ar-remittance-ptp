import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { dateTime } from "../data/labels";

interface AuditFilters {
  from_date?: string;
  to_date?: string;
  actor?: string;
  action?: string;
  entity_type?: string;
  q?: string;
}

export default function Audit() {
  const { ds } = useAuth();
  const [filters, setFilters] = useState<AuditFilters>({});
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => setPage(1), [filters]);
  const set = (patch: AuditFilters) => setFilters((f) => ({ ...f, ...patch }));
  const { data, isFetching } = useQuery({
    queryKey: ["audit", filters, page],
    queryFn: () => ds.audit({ ...filters, page, page_size: 50 }),
    placeholderData: keepPreviousData,
  });
  const total = data?.total ?? 0;
  return (
    <div className="page active" id="page-audit">
      <div className="page-content">
        <div className="page-header">
          <h1>📋 Audit Trail</h1>
          <p>Who did what, and when - system steps, logins and user actions</p>
        </div>
        <div className="filters-bar">
          <div className="filters-bar-header">
            <h3>🔽 Filters</h3>
            <button className="filter-btn btn-reset" onClick={() => setFilters({})}>Reset Filters</button>
          </div>
          <div className="filters-row">
            <div className="filter-group"><label htmlFor="a-from">From Date</label><input id="a-from" type="date" value={filters.from_date ?? ""} onChange={(e) => set({ from_date: e.target.value || undefined })} /></div>
            <div className="filter-group"><label htmlFor="a-to">To Date</label><input id="a-to" type="date" value={filters.to_date ?? ""} onChange={(e) => set({ to_date: e.target.value || undefined })} /></div>
            <div className="filter-group"><label htmlFor="a-actor">Actor</label><input id="a-actor" type="text" placeholder="system or user" value={filters.actor ?? ""} onChange={(e) => set({ actor: e.target.value || undefined })} /></div>
            <div className="filter-group"><label htmlFor="a-action">Action</label><input id="a-action" type="text" placeholder="e.g. LOGIN_OK" value={filters.action ?? ""} onChange={(e) => set({ action: e.target.value || undefined })} /></div>
            <div className="filter-group">
              <label htmlFor="a-type">Entity</label>
              <select id="a-type" value={filters.entity_type ?? ""} onChange={(e) => set({ entity_type: e.target.value || undefined })}>
                <option value="">All</option><option value="email">E-mail</option><option value="work_item">Work item</option><option value="auth">Login</option><option value="ptp">PTP</option>
              </select>
            </div>
            <div className="filter-group"><label htmlFor="a-q">Search</label><input id="a-q" type="text" placeholder="Entity, action, actor" value={filters.q ?? ""} onChange={(e) => set({ q: e.target.value || undefined })} /></div>
          </div>
        </div>
        <div style={{ margin: "-6px 0 10px", fontSize: 12, color: "var(--c-text3)" }}>{isFetching ? "Loading…" : `${total.toLocaleString("en-US")} entries`}</div>
        <div className="table-card">
          <div className="table-wrap audit-table-wrap" style={{ maxHeight: 640, overflow: "auto" }}>
            <table>
              <thead><tr><th>When</th><th>Actor</th><th>Entity</th><th>ID</th><th>Action</th><th /></tr></thead>
              <tbody>
                {(data?.items ?? []).map((a) => (
                  <Fragment key={a.id}>
                    <tr className="clickable-row" onClick={() => setOpen(open === a.id ? null : a.id)}>
                      <td>{dateTime(a.occurred_at)}</td>
                      <td>{a.actor}{a.actor_role ? ` (${a.actor_role.replace(/_/g, " ")})` : ""}</td>
                      <td>{a.entity_type}</td>
                      <td className="font-mono">{a.entity_id ?? "—"}</td>
                      <td>{a.action.replace(/_/g, " ")}</td>
                      <td>{a.details ? (open === a.id ? "▾" : "▸") : ""}</td>
                    </tr>
                    {open === a.id && a.details && (
                      <tr><td colSpan={6}><pre className="email-body" style={{ maxHeight: 180 }}>{JSON.stringify(a.details, null, 2)}</pre></td></tr>
                    )}
                  </Fragment>
                ))}
                {data && data.items.length === 0 && <tr><td colSpan={6}><div className="empty-state">No audit entries match these filters.</div></td></tr>}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span>Page {page} of {Math.max(1, Math.ceil(total / 50))}</span>
            <span>
              <button className="page-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>{" "}
              <button className="page-btn" disabled={page * 50 >= total} onClick={() => setPage((p) => p + 1)}>Next ›</button>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
