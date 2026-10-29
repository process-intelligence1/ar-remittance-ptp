import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type ColumnDef, flexRender, getCoreRowModel, type VisibilityState, useReactTable } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { runAction } from "../components/ActionButtons";
import FilterBar from "../components/Filters";
import { useToast } from "../components/Toasts";
import type { ActionCode, Filters, WorkItemRow } from "../data";
import { ACTION_LABELS, CLASS_LABELS, STATUS_BADGE, STATUS_LABELS, dateTime, money } from "../data/labels";
import RecordDetail from "./RecordDetail";

const COLUMN_KEY = "ar_queue_columns";
const SORTABLE: Record<string, string> = {
  entry_id: "entry_id", received_at: "received_at", customer_name: "customer", company_code: "company_code", amount: "amount",
  confidence: "confidence", status: "status", classification: "classification", sla_due_at: "sla_due_at",
};

function Confidence({ v, source }: { v: number | null; source: string | null }) {
  if (v === null) return <>—</>;
  const cls = v >= 80 ? "high" : v >= 40 ? "medium" : "low";
  return (
    <span className="conf-bar-wrap" title={source ? `Confidence source: ${source}` : undefined}>
      <span className="conf-bar-track"><span className={`conf-bar-fill ${cls}`} style={{ width: `${Math.min(100, v)}%` }} /></span>
      <span className="conf-pct">{v.toFixed(1)}%</span>
    </span>
  );
}

const COLUMNS: ColumnDef<WorkItemRow>[] = [
  { id: "entry_id", header: "Entry ID", cell: (c) => <span className="font-mono">{c.row.original.entry_id}</span> },
  { id: "email_ref", header: "Email ID", cell: (c) => <span className="font-mono">{c.row.original.email_ref}</span> },
  { id: "received_at", header: "Received", cell: (c) => dateTime(c.row.original.received_at) },
  { id: "sender_email", header: "Sender", cell: (c) => c.row.original.sender_email ?? "—" },
  { id: "customer_name", header: "Customer", cell: (c) => c.row.original.customer_name ?? "(unidentified)" },
  { id: "company_code", header: "Co. Code", cell: (c) => c.row.original.company_code ?? "—" },
  { id: "region", header: "Region", cell: (c) => c.row.original.region ?? "—" },
  { id: "classification", header: "Classification", cell: (c) => CLASS_LABELS[c.row.original.classification] ?? c.row.original.classification },
  { id: "invoice_ref", header: "Invoice No.", cell: (c) => <span className="font-mono">{c.row.original.invoice_ref ?? "—"}</span> },
  { id: "match_field", header: "Match_Field", cell: (c) => c.row.original.match_field ?? "—" },
  { id: "match_level", header: "Match_Level", cell: (c) => c.row.original.match_level ?? "—" },
  { id: "bsid_match", header: "BSID Match", cell: (c) => <span className={`badge ${c.row.original.bsid_match ? "badge-bsid-yes" : "badge-bsid-no"}`}>{c.row.original.bsid_match ? "Yes" : "No"}</span> },
  { id: "amount", header: "Amount", cell: (c) => money(c.row.original.amount, c.row.original.currency) },
  {
    id: "amount_usd",
    header: "USD",
    cell: (c) => {
      const r = c.row.original;
      return r.usd_status === "NO_RATE" ? <span className="usd-flag" title="No exchange rate for this currency and date">no rate</span> : money(r.amount_usd);
    },
  },
  { id: "confidence", header: "Confidence", cell: (c) => <Confidence v={c.row.original.confidence} source={c.row.original.confidence_source} /> },
  { id: "status", header: "Status", cell: (c) => <span className={`badge ${STATUS_BADGE[c.row.original.status] ?? ""}`}>{STATUS_LABELS[c.row.original.status] ?? c.row.original.status}</span> },
  { id: "recommended_action", header: "Recommended Action", cell: (c) => c.row.original.recommended_action ?? "—" },
  { id: "assigned_role", header: "Assigned To", cell: (c) => c.row.original.assigned_role?.replace(/_/g, " ") ?? "—" },
  { id: "sla_due_at", header: "SLA Due", cell: (c) => dateTime(c.row.original.sla_due_at) },
];

const DEFAULT_HIDDEN: VisibilityState = { email_ref: false, sender_email: false, region: false, assigned_role: false, sla_due_at: false, amount_usd: false };

function loadVisibility(): VisibilityState {
  try {
    const raw = localStorage.getItem(COLUMN_KEY);
    return raw ? (JSON.parse(raw) as VisibilityState) : DEFAULT_HIDDEN;
  } catch {
    return DEFAULT_HIDDEN;
  }
}

export default function Queue() {
  const { ds, session } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sort, setSort] = useState<{ id: string; desc: boolean }>({ id: "received_at", desc: true });
  const [selected, setSelected] = useState<Map<number, WorkItemRow>>(new Map());
  const [visibility, setVisibility] = useState<VisibilityState>(loadVisibility);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [bulkAction, setBulkAction] = useState<ActionCode | "">("");

  useEffect(() => setPage(1), [filters, pageSize]);
  const query = useQuery({
    queryKey: ["workItems", filters, page, pageSize, sort],
    queryFn: () => ds.workItems({ ...filters, page, page_size: pageSize, sort: SORTABLE[sort.id] ?? "received_at", order: sort.desc ? "desc" : "asc" }),
    placeholderData: keepPreviousData,
  });
  const rows = query.data?.items ?? [];
  const total = query.data?.total ?? 0;

  const table = useReactTable({
    data: rows, columns: COLUMNS, getCoreRowModel: getCoreRowModel(), state: { columnVisibility: visibility },
    onColumnVisibilityChange: (u) => setVisibility((v) => { const next = typeof u === "function" ? u(v) : u; try { localStorage.setItem(COLUMN_KEY, JSON.stringify(next)); } catch { /* not saved */ } return next; }),
    getRowId: (r) => String(r.id),
  });

  const toggle = (r: WorkItemRow, on: boolean) => setSelected((m) => { const n = new Map(m); if (on) n.set(r.id, r); else n.delete(r.id); return n; });
  const pageAllSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const selectedRows = [...selected.values()];
  // only actions valid for EVERY selected row are offered
  const bulkActions = useMemo(() => {
    if (selectedRows.length === 0) return [] as ActionCode[];
    return selectedRows.map((r) => r.allowed_actions).reduce((a, b) => a.filter((x) => b.includes(x)));
  }, [selectedRows]);
  useEffect(() => { if (bulkAction && !bulkActions.includes(bulkAction)) setBulkAction(""); }, [bulkActions, bulkAction]);

  const openId = params.get("record");
  const open = (r: WorkItemRow) => setParams({ record: r.entry_id });
  const close = () => setParams({});
  const sortBy = (id: string) => SORTABLE[id] && setSort((s) => ({ id, desc: s.id === id ? !s.desc : true }));

  const apply = () => bulkAction && runAction(ds, toast, bulkAction, selectedRows.map((r) => r.id));

  return (
    <div className="page active" id="page-queue">
      <div className="page-content">
        <div className="page-header">
          <h1>⚡ Action Queue</h1>
          <p>Operational workbench — review, approve and process AR records</p>
        </div>
        <FilterBar value={filters} onChange={setFilters} extra="queue" />
        <div style={{ margin: "-6px 0 10px", fontSize: 12, color: "var(--c-text3)" }}>{query.isFetching ? "Loading…" : `${total.toLocaleString("en-US")} record(s)`}</div>

        <div className="bulk-action-bar" style={{ display: "flex" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, fontWeight: 600 }}>
              <input type="checkbox" checked={pageAllSelected} onChange={(e) => rows.forEach((r) => toggle(r, e.target.checked))} />
              Select all on this page
            </label>
            <span style={{ fontSize: 12, color: "var(--c-text3)" }}>{selected.size} selected</span>
            <select aria-label="Bulk action" value={bulkAction} onChange={(e) => setBulkAction(e.target.value as ActionCode | "")} disabled={bulkActions.length === 0} style={{ height: 32, minWidth: 250, padding: "0 10px", border: "1px solid var(--c-border)", borderRadius: 6 }}>
              <option value="">{selected.size ? "Select bulk action" : "Select records first"}</option>
              {bulkActions.map((a) => <option key={a} value={a}>{ACTION_LABELS[a]}{a === "CONFIRM_EXTRACT_EXCEL" ? ` (${selected.size})` : ""}</option>)}
            </select>
            <button type="button" className="filter-btn btn-apply" disabled={!bulkAction} onClick={apply}>Apply to Selected</button>
            <button type="button" className="filter-btn btn-reset" onClick={() => setSelected(new Map())}>Clear Selection</button>
          </div>
          <span style={{ fontSize: 11, color: "var(--c-text4)" }}>Only actions valid for every selected record are offered.</span>
        </div>

        <div className="table-card">
          <div className="table-card-header">
            <h3>Records</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <div className="column-picker">
                <button type="button" className="column-picker-btn" onClick={() => setPickerOpen((o) => !o)}>☷ Columns ▾</button>
                {pickerOpen && (
                  <div className="column-picker-menu" style={{ display: "block" }}>
                    <div className="column-picker-head">
                      <span>Show columns</span>
                      <button type="button" onClick={() => table.toggleAllColumnsVisible(true)}>All</button>
                      <button type="button" onClick={() => table.toggleAllColumnsVisible(false)}>None</button>
                    </div>
                    {table.getAllLeafColumns().map((c) => (
                      <label key={c.id} className="column-picker-option">
                        <input type="checkbox" checked={c.getIsVisible()} onChange={c.getToggleVisibilityHandler()} /> {String(c.columnDef.header)}
                      </label>
                    ))}
                  </div>
                )}
              </div>
              <select className="per-page-select" aria-label="Rows per page" value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
                {[25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}
              </select>
            </div>
          </div>
          <div className="table-wrap queue-table-wrap" style={{ maxHeight: 600, overflow: "auto" }}>
            <table>
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    <th style={{ width: 32 }} />
                    {hg.headers.map((h) => (
                      <th key={h.id} className={SORTABLE[h.column.id] ? "sortable" : undefined} onClick={() => sortBy(h.column.id)}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {sort.id === h.column.id ? (sort.desc ? " ▼" : " ▲") : ""}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="clickable-row" onClick={() => open(row.original)}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" aria-label={`Select ${row.original.entry_id}`} checked={selected.has(row.original.id)} onChange={(e) => toggle(row.original, e.target.checked)} />
                    </td>
                    {row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}
                  </tr>
                ))}
                {!query.isLoading && rows.length === 0 && (
                  <tr><td colSpan={30}><div className="empty-state">No records match these filters.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span>Page {page} of {Math.max(1, Math.ceil(total / pageSize))}</span>
            <span>
              <button className="page-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>{" "}
              <button className="page-btn" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)}>Next ›</button>
            </span>
          </div>
        </div>
      </div>
      {openId && session && <RecordDetail id={openId} onClose={close} />}
    </div>
  );
}
