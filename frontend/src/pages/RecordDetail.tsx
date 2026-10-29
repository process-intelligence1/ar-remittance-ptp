import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import ActionButtons, { runAction } from "../components/ActionButtons";
import { useToast } from "../components/Toasts";
import type { ActionCode, Attachment, AuditRow, Candidate, WorkItemDetail } from "../data";
import { evidenceBoxes } from "../data/evidence";
import { CLASS_LABELS, STATUS_BADGE, STATUS_LABELS, dateTime, money } from "../data/labels";

const IMAGE = /^image\/(png|jpe?g|gif|tiff?)$/;

function Viewer({ attachments, evidence }: { attachments: Attachment[]; evidence: ReturnType<typeof evidenceBoxes> }) {
  const { ds } = useAuth();
  const withEvidence = attachments.find((a) => evidence.some((e) => e.attachmentId === a.id));
  const [selected, setSelected] = useState<number | undefined>(withEvidence?.id ?? attachments[0]?.id);
  const [pageNo, setPageNo] = useState(1);
  const att = attachments.find((a) => a.id === selected);
  useEffect(() => setPageNo(1), [selected]);
  if (!att) return <div className="text-muted text-xs">This e-mail has no attachments - the data was read from the e-mail text.</div>;

  const isImage = IMAGE.test(att.mime_type ?? "");
  const src = att.page_url ? ds.resolveUrl(att.page_url.replace("{page}", String(pageNo))) : isImage ? ds.resolveUrl(att.url) : null;
  const boxes = evidence.filter((e) => e.attachmentId === att.id && e.page === pageNo);
  const pages = att.page_count ?? 1;
  return (
    <div>
      {attachments.length > 1 && (
        <div className="att-tabs">
          {attachments.map((a) => (
            <button key={a.id} className={a.id === att.id ? "active" : ""} onClick={() => setSelected(a.id)}>{a.filename}</button>
          ))}
        </div>
      )}
      <div className="hl-legend">
        {att.filename} · {boxes.length > 0 ? `${boxes.length} highlighted value(s) on this page` : "no highlighted values on this page"}
        {" · "}
        <a href={ds.resolveUrl(att.url)} target="_blank" rel="noreferrer">open / download</a>
      </div>
      {src ? (
        <div className="viewer">
          <img src={src} alt={`${att.filename} page ${pageNo}`} />
          {boxes.map((b, i) => (
            <div key={i} className="hl" title={`${b.label}: ${b.text}`} style={{ left: `${b.bbox[0] * 100}%`, top: `${b.bbox[1] * 100}%`, width: `${(b.bbox[2] - b.bbox[0]) * 100}%`, height: `${(b.bbox[3] - b.bbox[1]) * 100}%` }} />
          ))}
        </div>
      ) : (
        <TextView attachment={att} />
      )}
      {pages > 1 && src && (
        <div className="pager">
          <button className="page-btn" disabled={pageNo <= 1} onClick={() => setPageNo((p) => p - 1)}>‹ Prev page</button>
          <span>Page {pageNo} of {pages}</span>
          <button className="page-btn" disabled={pageNo >= pages} onClick={() => setPageNo((p) => p + 1)}>Next page ›</button>
        </div>
      )}
      {boxes.length > 0 && <div className="hl-legend">{[...new Set(boxes.map((b) => b.label))].join(", ")}</div>}
    </div>
  );
}

function TextView({ attachment }: { attachment: Attachment }) {
  const { ds } = useAuth();
  const q = useQuery({ queryKey: ["attachmentLayout", attachment.id], queryFn: () => ds.attachmentLayout(attachment.id) });
  if (q.isLoading) return <div className="text-muted text-xs">Loading text…</div>;
  return <pre className="email-body">{q.data?.text || "(no text could be read from this file)"}</pre>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{children ?? "—"}</span>
    </div>
  );
}

const SCORE_LABELS: [string, string][] = [
  ["invoice_match_score", "Invoice match (×0.35)"],
  ["amount_alignment_score", "Amount alignment (×0.30)"],
  ["sender_company_score", "Sender → company code (×0.10)"],
  ["customer_name_similarity", "Customer name (×0.05)"],
  ["date_proxy_score", "Date proximity (×0.10)"],
];

function Scores({ d }: { d: WorkItemDetail }) {
  const s = d.score_breakdown;
  return (
    <div>
      {SCORE_LABELS.map(([k, label]) => {
        const v = Number(s[k] ?? 0);
        return (
          <div className="conf-component" key={k}>
            <span>{label}</span>
            <span className="conf-component-bar"><span className="conf-component-bar-fill" style={{ width: `${Math.round(v * 100)}%` }} /></span>
            <span className="font-mono">{v.toFixed(3)}</span>
          </div>
        );
      })}
      <Field label="Raw score">{s.raw_score !== null ? Number(s.raw_score).toFixed(3) : null}</Field>
      <Field label="Formula confidence (raw ÷ 0.90)">{s.formula_confidence !== null ? `${Number(s.formula_confidence).toFixed(1)}%` : null}</Field>
      <Field label="Fast path">{s.fast_path_override ? String(s.fast_path_override) : "not applied"}</Field>
      <Field label="Confidence (max of fast path and formula)">
        {s.confidence_score !== null ? `${Number(s.confidence_score).toFixed(1)}% (${s.confidence_source ?? "—"})` : null}
      </Field>
    </div>
  );
}

function Candidates({ list }: { list: Candidate[] }) {
  if (list.length === 0) return <div className="text-muted text-xs">No candidate BSID items.</div>;
  return (
    <table>
      <thead><tr><th>#</th><th>Document</th><th>Invoice ref (XBLNR)</th><th>Amount</th><th>Level</th><th>Confidence</th></tr></thead>
      <tbody>
        {list.map((c) => {
          const it = c.bsid_item as Record<string, string | number | null> | null;
          return (
            <tr key={c.rank} style={c.chosen ? { background: "var(--c-primary-bg)" } : undefined}>
              <td>{c.rank}{c.chosen ? " ✓" : ""}</td>
              <td className="font-mono">{it?.belnr ?? "—"}</td>
              <td className="font-mono">{it?.xblnr ?? "—"}</td>
              <td>{it ? money(Number(it.wrbtr), String(it.waers)) : "—"}</td>
              <td>{String((c.scores as Record<string, unknown>).level ?? "—")}</td>
              <td>{c.confidence_score !== null ? `${Number(c.confidence_score).toFixed(1)}%` : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Timeline({ rows }: { rows: AuditRow[] }) {
  if (rows.length === 0) return <div className="text-muted text-xs">No audit entries.</div>;
  return (
    <div className="audit-timeline">
      {rows.map((a) => (
        <div className="audit-step" key={a.id}>
          <div className="audit-step-icon">{a.actor === "system" ? "⚙" : "👤"}</div>
          <div className="audit-step-content">
            <strong>{a.action.replace(/_/g, " ")}</strong> · {a.actor}
            <div className="text-xs text-muted">{dateTime(a.occurred_at)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function RecordDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { ds } = useAuth();
  const toast = useToast();
  const { data: d, isLoading, error } = useQuery({ queryKey: ["workItem", id], queryFn: () => ds.workItem(id) });
  const boxes = useMemo(() => evidenceBoxes(d?.evidence), [d?.evidence]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay open" style={{ display: "flex" }} onClick={onClose}>
      <div className="modal-panel wide" role="dialog" aria-label="Record Detail" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Record Detail {d ? `· ${d.entry_id}` : ""}</h2>
          <button className="modal-close" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {isLoading && <div className="empty-state">Loading…</div>}
          {error && <div className="empty-state">Could not load this record: {(error as Error).message}</div>}
          {d && (
            <>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                <span className={`badge ${STATUS_BADGE[d.status] ?? ""}`}>{STATUS_LABELS[d.status] ?? d.status}</span>
                <span className="badge">{CLASS_LABELS[d.classification] ?? d.classification}</span>
                {d.match_level && <span className="badge">Invoice match: {d.match_level}{d.match_field ? ` (${d.match_field})` : ""}</span>}
                {d.duplicate_of && <span className="badge badge-duplicate">Duplicate of {d.duplicate_of}</span>}
              </div>
              {(d.review_reasons?.length || d.exception_reason) && (
                <div className="ai-explanation" style={{ marginBottom: 12 }}>
                  <strong>Why this needs attention:</strong> {[d.exception_reason, ...(d.review_reasons ?? [])].filter(Boolean).join(" · ")}
                </div>
              )}
              <div className="modal-section">
                <div className="modal-section-title">Actions</div>
                <ActionButtons actions={d.allowed_actions} onAction={(a: ActionCode) => runAction(ds, toast, a, [d.id])} />
                {d.recommended_action && <div className="text-xs text-muted" style={{ marginTop: 6 }}>Recommended: {d.recommended_action}</div>}
              </div>
              <div className="detail-columns">
                <div>
                  <div className="modal-section">
                    <div className="modal-section-title">Original e-mail</div>
                    <Field label="From">{String(d.email.sender_name ?? "")} {d.sender_email ? `<${d.sender_email}>` : ""}</Field>
                    <Field label="Subject">{d.subject}</Field>
                    <Field label="Received">{dateTime(d.received_at)}</Field>
                    <pre className="email-body">{String(d.email.body_text_clean ?? d.email.body_text ?? "")}</pre>
                  </div>
                  <div className="modal-section">
                    <div className="modal-section-title">Attachment viewer (extracted values highlighted)</div>
                    <Viewer key={d.id} attachments={d.attachments} evidence={boxes} />
                  </div>
                </div>
                <div>
                  <div className="modal-section">
                    <div className="modal-section-title">Extracted fields</div>
                    <Field label="Customer">{d.customer_name ? `${d.customer_name} (${(d.kunnr ?? "").replace(/^0+/, "")})` : "(unidentified)"}</Field>
                    <Field label="Company code / region">{`${d.company_code ?? "—"} / ${d.region ?? "—"}`}</Field>
                    <Field label="Invoice number">{d.invoice_ref}</Field>
                    <Field label="Amount">{money(d.amount, d.currency)}{d.usd_status === "OK" && d.currency !== "USD" ? ` (≈ ${money(d.amount_usd)} USD)` : d.usd_status === "NO_RATE" ? " (no exchange rate)" : ""}</Field>
                    <Field label="Payment date">{String(d.work_item.payment_date ?? "—")}</Field>
                    <Field label="Payment reference">{String(d.work_item.remittance_ref ?? "—")}</Field>
                    <Field label="Promise date">{String(d.work_item.promise_date ?? "—")}</Field>
                    <Field label="Deduction">{d.work_item.deduction_amount ? `${d.work_item.deduction_amount} (${d.work_item.deduction_reason ?? "—"})` : "—"}</Field>
                    <Field label="Assigned to">{d.assigned_role?.replace(/_/g, " ")}</Field>
                    <Field label="SLA due">{dateTime(d.sla_due_at)}</Field>
                  </div>
                  <div className="modal-section">
                    <div className="modal-section-title">Match &amp; score breakdown</div>
                    <Scores d={d} />
                  </div>
                  <div className="modal-section">
                    <div className="modal-section-title">BSID candidates</div>
                    <Candidates list={d.candidates} />
                  </div>
                  {d.same_email_items.length > 0 && (
                    <div className="modal-section">
                      <div className="modal-section-title">Other rows from the same e-mail</div>
                      {d.same_email_items.map((s) => (
                        <div key={s.id} className="text-xs"><span className="font-mono">{s.entry_id}</span> · {s.invoice_ref ?? "—"} · {STATUS_LABELS[s.status] ?? s.status}</div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="modal-section">
                <div className="modal-section-title">Audit timeline</div>
                <Timeline rows={d.audit} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
