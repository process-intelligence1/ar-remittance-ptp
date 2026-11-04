import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toasts";
import type { DemoSample, WorkerStart } from "../data";
import { dateOnly, dateTime } from "../data/labels";

const KIND: Record<string, string> = { O: "Out of scope", P: "Promise to pay", R: "Remittance" };
function scenarioLabel(code: string): string {
  if (code.startsWith("P03R") || code.startsWith("P05R")) return "Payment after a promise";
  if (code.startsWith("P06")) return "Payment + promise";
  return KIND[code[0]] ?? "";
}

const workerNote = (w: WorkerStart | null | undefined): string =>
  !w ? "" : w.started ? " The worker was started - it is processed within about a minute." : ` (Worker not started: ${w.reason ?? "unknown"} - the next scheduled run picks it up.)`;

function Card({ title, children, danger }: { title: string; children: React.ReactNode; danger?: boolean }) {
  return (
    <div className="table-card" style={{ padding: 18, marginBottom: 16, borderColor: danger ? "#fecaca" : undefined }}>
      <h3 style={{ margin: "0 0 10px", fontSize: 15, color: danger ? "var(--c-danger)" : undefined }}>{title}</h3>
      {children}
    </div>
  );
}

/** Demo Control: the presenter's panel - move the business date, send a sample, start processing, reset to the saved starting point. */
export default function DemoControl() {
  const { ds } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const state = useQuery({ queryKey: ["demo", "state"], queryFn: () => ds.demoState() });
  const d = state.data;
  const [busy, setBusy] = useState<string | null>(null);
  const [pickedDate, setPickedDate] = useState("");
  const [processNow, setProcessNow] = useState(true);
  const [filter, setFilter] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    for (const k of ["demo", "ptp", "workItems", "workItem", "kpis", "audit", "exported"]) qc.invalidateQueries({ queryKey: [k] });
  };
  const run = async (key: string, work: () => Promise<string>) => {
    setBusy(key);
    setError(null);
    try {
      toast(await work(), "success");
      refresh();
    } catch (e) {
      const m = e instanceof Error ? e.message : "That did not work.";
      setError(m);
      toast(m, "error");
    } finally {
      setBusy(null);
    }
  };

  const moveDate = (change: { date: string } | { add_days: number }) =>
    run("date", async () => {
      const r = await ds.demoSetBusinessDate(change);
      const p = r.ptp;
      return `Business date is now ${dateOnly(r.business_date)}. Promises checked: ${p.changed.length} changed, ${p.alerts} alert(s) and ${p.escalations} escalation(s) e-mailed.${workerNote(r.worker)}`;
    });

  const rows = (d?.live_set ?? []).filter((s) => !filter || `${s.code} ${s.subject} ${s.from} ${scenarioLabel(s.code)}`.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="page active" id="page-demo">
      <div className="page-content">
        <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h1>🎛️ Demo Control</h1>
            <p>
              Business date: <strong data-testid="demo-date">{d ? dateOnly(d.business_date) : "…"}</strong> ·{" "}
              {d?.reset_point ? <>reset point from {dateTime(d.reset_point.taken_at)} ({d.reset_point.counts["ar.work_item"] ?? "?"} work items)</> : "no reset point yet"}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="filter-btn btn-reset" disabled={!!busy} onClick={() => run("process", async () => { const w = await ds.demoProcessNow(); return w.started ? "Worker started." : `Worker not started: ${w.reason ?? "unknown"}`; })}>⚙ Process now</button>
            <button type="button" className="dlg-btn danger" disabled={!!busy || !d?.reset_point} onClick={() => setConfirmReset(true)} data-testid="demo-reset"
              title="Brings everything back to the saved starting point: statuses, exported cases, promises, samples sent and the business date">♻ Reset demo…</button>
          </div>
        </div>
        {error && <div className="dlg-error" role="alert">{error}</div>}

        <Card title="📅 Business date">
          <p className="text-xs text-muted" style={{ marginTop: 0 }}>
            Every rule uses this date, not today's. Moving it forward makes promises fall due: they become broken and escalated, and the alert e-mails go out (to the demo mailbox only).
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            {[1, 3, 7, 30].map((n) => (
              <button key={n} type="button" className="filter-btn btn-apply" disabled={!!busy} onClick={() => moveDate({ add_days: n })}>+{n} day{n > 1 ? "s" : ""}</button>
            ))}
            <input type="date" aria-label="Business date" value={pickedDate} onChange={(e) => setPickedDate(e.target.value)} style={{ height: 32, padding: "0 8px", border: "1px solid var(--c-border)", borderRadius: 6 }} />
            <button type="button" className="filter-btn btn-apply" disabled={!!busy || !pickedDate} onClick={() => moveDate({ date: pickedDate })}>Set date</button>
            <button type="button" className="filter-btn btn-reset" disabled={!!busy || !d} onClick={() => d && moveDate({ date: d.default_business_date })}>Back to {d ? dateOnly(d.default_business_date) : "default"}</button>
          </div>
        </Card>

        <Card title="📨 Send a sample e-mail">
          <p className="text-xs text-muted" style={{ marginTop: 0 }}>
            The sample is put into the Gmail inbox with the customer as sender. The system reads it like any e-mail and it shows up in the Action Queue.
            {d?.sent_total ? ` ${d.sent_total} sent since the last reset.` : ""}
          </p>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
            <input aria-label="Filter samples" placeholder="Filter by code, customer or subject…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ height: 32, padding: "0 10px", border: "1px solid var(--c-border)", borderRadius: 6, minWidth: 260 }} />
            <label style={{ fontSize: 13, display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={processNow} onChange={(e) => setProcessNow(e.target.checked)} /> Start processing right away
            </label>
          </div>
          {d?.live_set_error && <div className="dlg-error">{d.live_set_error}</div>}
          <div className="table-wrap" style={{ maxHeight: 420, overflow: "auto" }}>
            <table>
              <thead><tr><th>Code</th><th>Type</th><th>From</th><th>Subject</th><th>Files</th><th>Sent</th><th /></tr></thead>
              <tbody>
                {rows.map((s: DemoSample) => (
                  <tr key={s.code}>
                    <td className="font-mono">{s.code}</td>
                    <td>{scenarioLabel(s.code)}</td>
                    <td style={{ fontSize: 12 }}>{s.from ?? "—"}</td>
                    <td style={{ fontSize: 12 }}>{s.subject ?? "—"}</td>
                    <td style={{ fontSize: 12 }}>{s.attachments.length ? s.attachments.join(", ") : "text only"}</td>
                    <td style={{ fontSize: 12 }}>{s.sent_count ? `${s.sent_count}× · ${dateTime(s.last_sent_at)}` : "—"}</td>
                    <td>
                      <button type="button" className="filter-btn btn-apply" disabled={!!busy} aria-label={`Send ${s.code}`}
                        onClick={() => run(`send-${s.code}`, async () => { const r = await ds.demoSendSample(s.code, processNow); return `${r.code} sent to the inbox: “${r.subject ?? ""}”.${workerNote(r.worker)}`; })}>
                        {busy === `send-${s.code}` ? "Sending…" : "Send"}
                      </button>
                    </td>
                  </tr>
                ))}
                {d && rows.length === 0 && <tr><td colSpan={7}><div className="empty-state">No samples match.</div></td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

      </div>

      {confirmReset && (
        <div className="dlg-overlay" onClick={() => setConfirmReset(false)}>
          <div className="dlg" role="dialog" aria-label="Reset demo" onClick={(e) => e.stopPropagation()}>
            <div className="dlg-head"><h2>Reset demo?</h2><button className="modal-close" aria-label="Close" onClick={() => setConfirmReset(false)}>✕</button></div>
            <div className="dlg-body">
              <p style={{ marginTop: 0 }}>Everything changed since the reset point is lost: confirmed and rejected records, the exported-cases list, promise statuses, sent samples and the business date go back to the saved starting point ({d?.reset_point ? dateTime(d.reset_point.taken_at) : ""}).</p>
              <p className="text-xs text-muted">E-mails already in the Gmail inbox stay there. This cannot be undone.</p>
            </div>
            <div className="dlg-foot">
              <button className="dlg-btn" onClick={() => setConfirmReset(false)}>Cancel</button>
              <button className="dlg-btn danger" disabled={!!busy} onClick={() => { setConfirmReset(false); run("reset", async () => { const r = await ds.demoReset(); return `Demo reset to ${dateTime(r.reset_point_taken_at)}; business date ${dateOnly(r.business_date)}.`; }); }}>Reset demo</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
