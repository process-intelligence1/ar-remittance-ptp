import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toasts";
import type { PtpItem, PtpStatus } from "../data";
import { PTP_STATUS_BADGE, PTP_STATUS_LABELS, dateOnly, dateTime, money } from "../data/labels";

const ORDER: PtpStatus[] = ["OPEN", "PARTIALLY_KEPT", "KEPT", "BROKEN", "ESCALATED", "CANCELLED"];

function Alerts({ p }: { p: PtpItem }) {
  return (
    <span style={{ display: "inline-flex", gap: 6 }}>
      {p.alerted_at && <span title={`Collections alert e-mailed ${dateTime(p.alerted_at)}`} data-testid="alert-sent">📧 Alert</span>}
      {p.escalated_at && <span title={`Supervisor escalation e-mailed ${dateTime(p.escalated_at)}`} data-testid="escalation-sent">⬆ Escalated</span>}
      {!p.alerted_at && !p.escalated_at && "—"}
    </span>
  );
}

/** PTP Tracker: every promise to pay (one row per invoice or instalment) with its deadline, what was paid and the alerts sent. */
export default function PtpTracker() {
  const { ds } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [status, setStatus] = useState<string>("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ["ptp", status, q], queryFn: () => ds.ptpList({ status: status || undefined, q: q || undefined, page_size: 100 }) });
  const data = query.data;

  const recheck = async () => {
    setBusy(true);
    try {
      const r = await ds.runPtpChecks();
      toast(
        r.changed.length || r.alerts || r.escalations
          ? `Checked ${r.checked} promise(s) at ${r.business_date}: ${r.changed.length} changed, ${r.alerts} alert(s), ${r.escalations} escalation(s) e-mailed.`
          : `Checked ${r.checked} promise(s) at ${r.business_date}: nothing changed.`,
        "success",
      );
      qc.invalidateQueries({ queryKey: ["ptp"] });
    } catch (e) {
      toast(e instanceof Error ? e.message : "The check failed.", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page active" id="page-ptp">
      <div className="page-content">
        <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <div>
            <h1>🤝 PTP Tracker</h1>
            <p>Promises to pay: kept, partly kept, broken and escalated — checked at the business date{data ? ` (${dateOnly(data.business_date)})` : ""}</p>
          </div>
          <button type="button" className="filter-btn btn-apply" onClick={recheck} disabled={busy} data-testid="ptp-recheck">
            {busy ? "Checking…" : "↻ Re-check now"}
          </button>
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
          {ORDER.map((s) => (
            <button
              key={s}
              type="button"
              className={`badge ${PTP_STATUS_BADGE[s]}`}
              style={{ cursor: "pointer", padding: "8px 14px", fontSize: 13, outline: status === s ? "2px solid var(--c-primary)" : "none" }}
              onClick={() => setStatus((cur) => (cur === s ? "" : s))}
              aria-pressed={status === s}
              data-testid={`ptp-card-${s}`}
            >
              {PTP_STATUS_LABELS[s]}: <strong>{data?.counts[s] ?? "—"}</strong>
            </button>
          ))}
        </div>

        <div className="filters-bar">
          <div className="filters-row">
            <div className="filter-group">
              <label htmlFor="ptp-q">Search</label>
              <input id="ptp-q" type="text" placeholder="Entry ID, invoice, customer…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <div className="filter-group">
              <label htmlFor="ptp-status">Status</label>
              <select id="ptp-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All Statuses</option>
                {ORDER.map((s) => <option key={s} value={s}>{PTP_STATUS_LABELS[s]}</option>)}
              </select>
            </div>
            <div className="filter-group" style={{ justifyContent: "flex-end" }}>
              <span className="text-xs text-muted">{data ? `${data.total} promise(s) · grace ${data.grace_days} days` : "Loading…"}</span>
            </div>
          </div>
        </div>

        <div className="table-card">
          <div className="table-wrap" style={{ maxHeight: 640, overflow: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Entry ID</th><th>Customer</th><th>Invoice No.</th><th>Inst.</th><th>Promise Date</th><th>Last Day (grace)</th>
                  <th>Promised</th><th>Received</th><th>Status</th><th>Days Overdue</th><th>Alerts</th><th>Payments / Note</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((p) => (
                  <tr key={p.id} className="clickable-row" onClick={() => navigate(`/queue?record=${p.entry_id}`)}>
                    <td className="font-mono">{p.entry_id}</td>
                    <td>{p.customer_name ?? "(unidentified)"}</td>
                    <td className="font-mono">{p.invoice_ref ?? "—"}</td>
                    <td>{p.instalment_no}</td>
                    <td>{dateOnly(p.promise_date)}</td>
                    <td>{dateOnly(p.deadline)}</td>
                    <td>{money(p.amount, p.currency)}</td>
                    <td>{p.amount_received !== null ? money(p.amount_received, p.currency) : "—"}</td>
                    <td><span className={`badge ${PTP_STATUS_BADGE[p.status] ?? ""}`}>{PTP_STATUS_LABELS[p.status] ?? p.status}</span></td>
                    <td>{p.days_overdue > 0 ? p.days_overdue : "—"}</td>
                    <td><Alerts p={p} /></td>
                    <td style={{ fontSize: 12 }}>
                      {p.payments.map((x) => <div key={x.entry_id}><span className="font-mono">{x.entry_id}</span> {dateOnly(x.date)}: {x.applied} applied</div>)}
                      {p.check_note && <div className="text-muted">{p.check_note}</div>}
                      {p.payments.length === 0 && !p.check_note && "—"}
                    </td>
                  </tr>
                ))}
                {data && data.items.length === 0 && <tr><td colSpan={12}><div className="empty-state">No promises match these filters.</div></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
