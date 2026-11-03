import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import ActionButtons, { runAction } from "../components/ActionButtons";
import { useToast } from "../components/Toasts";
import type { ActionCode, Attachment, AuditRow, Candidate, WorkItemDetail } from "../data";
import { evidenceBoxes } from "../data/evidence";
import { aiExplanation, confidenceBadge, confidenceRows, fastPathBanner } from "../data/explain";
import { CLASS_LABELS, STATUS_BADGE, STATUS_LABELS, dateOnly, dateTime, money } from "../data/labels";

const IMAGE = /^image\/(png|jpe?g|gif|tiff?)$/;
const GREEN = "#059669";

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

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{children ?? "—"}</span>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <div className="modal-section" data-section={id}>
      <div className="modal-section-title">{title}</div>
      {children}
    </div>
  );
}

/** 1. SAP BSID Match - two-column grid like the prototype. */
function BsidMatch({ d }: { d: WorkItemDetail }) {
  const b = d.bsid;
  return (
    <Section id="bsid" title="🔗 SAP BSID Match">
      <span className={`badge ${b.matched ? "badge-bsid-yes" : "badge-bsid-no"}`}>{b.matched ? "BSID match: Yes" : "BSID match: No"}</span>
      <div style={{ marginTop: 10 }}>
        <div className="detail-grid">
          <Field label="BSID Invoice"><span className="font-mono">{b.invoice ?? "—"}</span></Field>
          <Field label="BSID Customer">{b.customer_name || b.customer_no ? `${b.customer_name ?? "—"} (${(b.customer_no ?? "").replace(/^0+/, "") || "—"})` : "—"}</Field>
          <Field label="BSID Company Code"><span className="font-mono">{b.company_code ?? "—"}</span></Field>
          <Field label="BSID Amount"><span className="font-mono">{b.amount !== undefined ? money(Number(b.amount), b.currency) : "—"}</span></Field>
          <Field label="BSID Currency">{b.currency ?? "—"}</Field>
          <Field label="BSID Posting Date">{dateOnly(b.posting_date)}</Field>
          <Field label="Open Item Status">{b.open_item_status ?? "—"}</Field>
          <Field label="Amount Difference">{b.amount_difference_pct !== null && b.amount_difference_pct !== undefined ? `${Number(b.amount_difference_pct).toFixed(3)}%` : "—"}</Field>
        </div>
        {d.exception_reason && (
          <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--c-danger-bg)", border: "1px solid #fecaca", borderRadius: 6, fontSize: 12, color: "var(--c-danger)" }}>
            ⚠️ Exception: {d.exception_reason}
          </div>
        )}
      </div>
    </Section>
  );
}

/** 2. Confidence Scoring - fast-path banner, one row per component with a green bar, final score with badge. */
function ConfidenceScoring({ d }: { d: WorkItemDetail }) {
  const banner = fastPathBanner(d);
  const badge = confidenceBadge(d);
  const final = d.score_breakdown.confidence_score === null ? null : Number(d.score_breakdown.confidence_score);
  return (
    <Section id="confidence" title="⚖️ Confidence Scoring">
      {banner && (
        <div style={{ background: "var(--c-primary-bg)", border: "1px solid #bfdbfe", borderRadius: 6, padding: "8px 12px", marginBottom: 12, fontSize: 12, color: "var(--c-primary)" }}>
          ⚡ <strong>{banner}</strong>
        </div>
      )}
      {confidenceRows(d).map((r) => (
        <div className="conf-component" key={r.key}>
          <div>
            <div className="comp-name">{r.name}</div>
            <div className="conf-explanation">{r.description}</div>
          </div>
          <div className="comp-weight">Weight {r.weight}</div>
          <div className="comp-score" style={{ color: GREEN }}>{(r.score * 100).toFixed(1)}%</div>
          <div className="conf-component-bar">
            <div className="conf-component-bar-fill" style={{ width: `${Math.min(100, r.score * 100)}%`, background: GREEN }} />
          </div>
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12, paddingTop: 10, borderTop: "2px solid var(--c-border)" }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>Final Confidence Score</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className={`badge ${badge.cls}`}>{badge.label}</span>
          <span style={{ fontSize: 20, fontWeight: 800, color: GREEN }}>{final !== null ? `${final.toFixed(1)}%` : "—"}</span>
        </div>
      </div>
      <div className="text-xs text-muted" style={{ marginTop: 6 }}>
        Raw score {d.score_breakdown.raw_score !== null ? Number(d.score_breakdown.raw_score).toFixed(3) : "—"} ÷ 0.90 = formula {d.score_breakdown.formula_confidence !== null ? `${Number(d.score_breakdown.formula_confidence).toFixed(1)}%` : "—"}
        {" · "}confidence = max(fast path, formula){d.confidence_source ? ` (${d.confidence_source})` : ""}
      </div>
    </Section>
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

function Pipeline({ d }: { d: WorkItemDetail }) {
  const conf = d.score_breakdown.confidence_score === null ? null : Number(d.score_breakdown.confidence_score);
  const labels = [CLASS_LABELS[d.classification] ?? d.classification, d.invoice_ref ?? "—", d.bsid.matched ? "Match" : "No Match", conf !== null ? `${conf.toFixed(1)}%` : "—", (d.decision ?? "—").replace(/_/g, " "), d.recommended_action ?? "—"];
  return (
    <div className="decision-pipeline">
      {["Classify", "Extract", "BSID Lookup", "Score", "Decision", "Action"].map((step, i) => (
        <div className="pipeline-step" key={step}>
          <div className="pipeline-node active" style={{ minWidth: 90 }}>
            <div style={{ fontSize: 10, fontWeight: 600 }}>{step}</div>
            <div style={{ fontSize: 9, color: "var(--c-text3)", marginTop: 2 }}>{labels[i]}</div>
          </div>
          {i < 5 && <span className="pipeline-arrow">→</span>}
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

              <div className="detail-columns">
                <div>
                  <Section id="email" title="📧 Email Details">
                    <Field label="From">{String(d.email.sender_name ?? "")} {d.sender_email ? `<${d.sender_email}>` : ""}</Field>
                    <Field label="Subject">{d.subject}</Field>
                    <Field label="Received">{dateTime(d.received_at)}</Field>
                    <pre className="email-body">{String(d.email.body_text_clean ?? d.email.body_text ?? "")}</pre>
                  </Section>
                  <Section id="extracted" title="🔍 Extracted Information">
                    <div className="detail-grid">
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
                  </Section>
                </div>
                <div>
                  <Section id="viewer" title="📎 Attachment Viewer (extracted values highlighted)">
                    <Viewer key={d.id} attachments={d.attachments} evidence={boxes} />
                  </Section>
                </div>
              </div>

              <BsidMatch d={d} />
              <ConfidenceScoring d={d} />

              <Section id="candidates" title="🧾 BSID Candidates">
                <Candidates list={d.candidates} />
                {d.same_email_items.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <div className="detail-label">Other rows from the same e-mail</div>
                    {d.same_email_items.map((s) => (
                      <div key={s.id} className="text-xs"><span className="font-mono">{s.entry_id}</span> · {s.invoice_ref ?? "—"} · {STATUS_LABELS[s.status] ?? s.status}</div>
                    ))}
                  </div>
                )}
              </Section>
              <Section id="pipeline" title="🔄 Decision Pipeline">
                <Pipeline d={d} />
              </Section>
              <Section id="audit" title="🕘 Audit Timeline">
                <Timeline rows={d.audit} />
              </Section>

              <Section id="explanation" title="🤖 AI Explanation">
                <div className="ai-explanation">
                  {aiExplanation(d).map((line, i) => (
                    <p key={i} style={{ margin: i ? "6px 0 0" : 0 }}>{line}</p>
                  ))}
                </div>
              </Section>
              <Section id="actions" title="⚡ Actions">
                <div style={{ marginBottom: 8 }}><span className={`badge ${STATUS_BADGE[d.status] ?? ""}`}>{STATUS_LABELS[d.status] ?? d.status}</span></div>
                <ActionButtons actions={d.allowed_actions} onAction={(a: ActionCode) => runAction(ds, toast, a, [d.id])} />
                {d.recommended_action && <div className="text-xs text-muted" style={{ marginTop: 6 }}>Recommended: {d.recommended_action}</div>}
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
