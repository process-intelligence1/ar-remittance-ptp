import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { ActionError, type ActionCode, type BsidChoice, type DetailsInput, type WorkItemRow } from "../data";
import { ACTION_LABELS, money } from "../data/labels";
import { useToast } from "./Toasts";

/** Actions that can be applied to several records at once (need no per-record input). */
export const BULK_ACTIONS: ActionCode[] = ["CONFIRM_ADD_EXCEL", "REJECT", "ESCALATE_TO_SUPERVISOR", "CLOSE_AS_DUPLICATE"];
const COMMENT_REQUIRED: ActionCode[] = ["REJECT", "ESCALATE_TO_SUPERVISOR"];
const DONE: Record<ActionCode, string> = {
  CONFIRM_ADD_EXCEL: "added to the Excel list (status Confirmed)",
  ADD_UPDATE_DETAILS: "updated and scored again",
  ADD_BSID_DETAILS: "updated and scored again",
  REJECT: "rejected",
  REQUEST_CLARIFICATION: "set to Awaiting Customer",
  ESCALATE_TO_SUPERVISOR: "escalated to the AR Supervisor",
  CLOSE_AS_DUPLICATE: "closed as duplicate",
  MARK_NON_DUPLICATE: "marked as not a duplicate and scored again",
};

function Shell({ title, wide, onClose, children, foot }: { title: string; wide?: boolean; onClose: () => void; children: ReactNode; foot: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="dlg-overlay" onClick={onClose}>
      <div className={`dlg ${wide ? "wide" : ""}`} role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="dlg-head">
          <h2>{title}</h2>
          <button className="modal-close" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="dlg-body">{children}</div>
        <div className="dlg-foot">{foot}</div>
      </div>
    </div>
  );
}

function Problems({ error }: { error: ActionError | Error | null }) {
  if (!error) return null;
  const problems = error instanceof ActionError ? error.problems : [];
  return (
    <div className="dlg-error" role="alert">
      {error.message}
      {problems.length > 0 && <ul style={{ margin: "6px 0 0 16px" }}>{problems.map((p) => <li key={p.entry_id}><span className="font-mono">{p.entry_id}</span>: {p.message}</li>)}</ul>}
    </div>
  );
}

type Submit = (go: () => Promise<string>) => void;

interface Common {
  rows: WorkItemRow[];
  action: ActionCode;
  onClose: () => void;
  submit: Submit;
  busy: boolean;
  error: Error | null;
}

/** Confirm, Reject, Escalate, Close as Duplicate, Mark as Non-Duplicate: a comment, then do it (one or many records). */
function CommentDialog({ rows, action, onClose, submit, busy, error }: Common) {
  const { ds } = useAuth();
  const [comment, setComment] = useState("");
  const required = COMMENT_REQUIRED.includes(action);
  const many = rows.length > 1;
  const run = () =>
    submit(async () => {
      const c = comment.trim() || undefined;
      if (many) {
        const r = await ds.performBulk({ action, comment: c, items: rows.map((x) => ({ id: x.id, version: x.version })) });
        return `${r.done} records ${DONE[action]}.`;
      }
      await ds.performAction(rows[0].id, { action, version: rows[0].version, comment: c });
      return `${rows[0].entry_id} ${DONE[action]}.`;
    });
  return (
    <Shell
      title={`${ACTION_LABELS[action]}${many ? ` (${rows.length} records)` : ""}`}
      onClose={onClose}
      foot={
        <>
          <button className="dlg-btn" onClick={onClose}>Cancel</button>
          <button className={`dlg-btn ${action === "REJECT" || action === "ESCALATE_TO_SUPERVISOR" ? "danger" : "primary"}`} disabled={busy || (required && !comment.trim())} onClick={run}>
            {busy ? "Working…" : ACTION_LABELS[action]}
          </button>
        </>
      }
    >
      <Problems error={error} />
      {action === "CONFIRM_ADD_EXCEL" && <div className="dlg-note">The record becomes <strong>Confirmed</strong> and is added to the Excel list (“Exported cases”). No SAP data is changed.</div>}
      <p style={{ fontSize: 13, marginTop: 0 }}>{many ? <>{rows.length} records: {rows.slice(0, 6).map((r) => r.entry_id).join(", ")}{rows.length > 6 ? ", …" : ""}</> : <><span className="font-mono">{rows[0].entry_id}</span> · {rows[0].customer_name ?? "(unidentified)"} · {rows[0].invoice_ref ?? "no invoice no."} · {money(rows[0].amount, rows[0].currency)}</>}</p>
      <div className="dlg-field">
        <label htmlFor="act-comment">Comment{required ? " (required)" : " (optional)"}</label>
        <textarea id="act-comment" value={comment} onChange={(e) => setComment(e.target.value)} autoFocus />
      </div>
    </Shell>
  );
}

/** Request Clarification: the e-mail written from the template in the customer's language; the analyst edits it, then it is sent. */
function ClarifyDialog({ rows, action, onClose, submit, busy, error }: Common) {
  const { ds } = useAuth();
  const row = rows[0];
  const [question, setQuestion] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const preview = useQuery({
    queryKey: ["emailPreview", row.id, question],
    queryFn: () => ds.previewEmail(row.id, question),
    placeholderData: (p) => p,
    refetchOnWindowFocus: false, // a refetch must not overwrite what the analyst is typing
  });
  const p = preview.data;
  useEffect(() => {
    if (p) {
      setSubject(p.subject);
      setBody(p.body);
    }
  }, [p?.subject, p?.body]); // eslint-disable-line react-hooks/exhaustive-deps
  const [draftQuestion, setDraftQuestion] = useState("");
  const send = () =>
    submit(async () => {
      const r = await ds.performAction(row.id, { action, version: row.version, email: { subject, body } });
      return `Clarification for ${row.entry_id} queued — delivered to ${p?.actual_recipient ?? "the demo mailbox"} only (${r.worker_started ? "sending now" : "sent with the next worker run"}).`;
    });
  return (
    <Shell
      title={`Request Clarification · ${row.entry_id}`}
      wide
      onClose={onClose}
      foot={
        <>
          <button className="dlg-btn" onClick={onClose}>Cancel</button>
          <button className="dlg-btn primary" disabled={busy || !p || !subject.trim() || !body.trim()} onClick={send}>{busy ? "Working…" : "Send e-mail"}</button>
        </>
      }
    >
      <Problems error={error} />
      {p && (
        <div className="dlg-note">
          Demo mode: this e-mail is meant for <strong>{p.intended_recipient}</strong> but is delivered to <strong>{p.actual_recipient}</strong> only. Template language: {p.language}.
        </div>
      )}
      {preview.isError && <div className="dlg-error">Could not prepare the e-mail: {(preview.error as Error).message}</div>}
      <div className="dlg-field">
        <label htmlFor="clar-q">Your question to the customer (optional - a standard question is used when empty)</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input id="clar-q" style={{ flex: 1 }} value={draftQuestion} onChange={(e) => setDraftQuestion(e.target.value)} />
          <button className="dlg-btn" type="button" onClick={() => setQuestion(draftQuestion)}>Update text</button>
        </div>
      </div>
      <div className="dlg-field">
        <label htmlFor="clar-s">Subject</label>
        <input id="clar-s" value={subject} onChange={(e) => setSubject(e.target.value)} />
      </div>
      <div className="dlg-field">
        <label htmlFor="clar-b">Text</label>
        <textarea id="clar-b" style={{ minHeight: 200 }} value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
    </Shell>
  );
}

const asText = (v: unknown) => (v === null || v === undefined ? "" : String(v));

/** Add / Update Invoice Details and Add BSID Invoice Details: change the fields, optionally pick a BSID item, save → matched and scored again. */
function DetailsDialog({ rows, action, onClose, submit, busy, error }: Common) {
  const { ds } = useAuth();
  const row = rows[0];
  const detail = useQuery({ queryKey: ["workItem", row.entry_id], queryFn: () => ds.workItem(row.entry_id) });
  const [form, setForm] = useState<Record<string, string> | null>(null);
  const [initial, setInitial] = useState<Record<string, string>>({});
  const [bsid, setBsid] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const choices = useQuery({ queryKey: ["bsidChoices", row.id, term], queryFn: () => ds.bsidChoices(row.id, term) });

  useEffect(() => {
    const d = detail.data;
    if (!d || form) return;
    const start = {
      invoice_ref: asText(d.invoice_ref),
      amount: asText(d.amount),
      currency: asText(d.currency),
      payment_date: asText(d.work_item.payment_date),
      payment_reference: asText(d.work_item.remittance_ref),
      kunnr: asText(d.kunnr).replace(/^0+/, ""),
      bukrs: asText(d.company_code),
    };
    setInitial(start);
    setForm(start);
  }, [detail.data, form]);

  const changed = form ? (Object.keys(form) as (keyof DetailsInput)[]).filter((k) => form[k] !== initial[k]) : [];
  const set = (k: string, v: string) => setForm((f) => ({ ...(f as Record<string, string>), [k]: v }));
  const save = () =>
    submit(async () => {
      const details: DetailsInput = {};
      for (const k of changed) (details as Record<string, string>)[k] = form![k];
      if (bsid !== null) details.bsid_id = bsid;
      await ds.performAction(row.id, { action, version: row.version, details });
      return `${row.entry_id} ${DONE[action]}.`;
    });

  const FIELDS: [string, string][] = [
    ["invoice_ref", "Invoice number"], ["amount", "Amount"], ["currency", "Currency"], ["payment_date", "Payment date (YYYY-MM-DD)"],
    ["payment_reference", "Payment reference"], ["kunnr", "Customer number"], ["bukrs", "Company code"],
  ];
  const pick = (c: BsidChoice) => setBsid((b) => (b === c.id ? null : c.id));
  return (
    <Shell
      title={`${ACTION_LABELS[action]} · ${row.entry_id}`}
      wide
      onClose={onClose}
      foot={
        <>
          <button className="dlg-btn" onClick={onClose}>Cancel</button>
          <button className="dlg-btn primary" disabled={busy || !form || (changed.length === 0 && bsid === null)} onClick={save}>{busy ? "Working…" : "Save and score again"}</button>
        </>
      }
    >
      <Problems error={error} />
      {detail.isLoading && <div className="text-muted text-xs">Loading…</div>}
      {form && (
        <>
          <div className="dlg-grid">
            {FIELDS.map(([k, label]) => (
              <div className="dlg-field" key={k}>
                <label htmlFor={`d-${k}`}>{label}</label>
                <input id={`d-${k}`} value={form[k]} onChange={(e) => set(k, e.target.value)} />
              </div>
            ))}
          </div>
          <div className="dlg-field">
            <label htmlFor="d-search">BSID item (optional) — the open items below are only listed here</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input id="d-search" style={{ flex: 1 }} placeholder="Invoice no., document no. or customer" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && setTerm(search)} />
              <button className="dlg-btn" type="button" onClick={() => setTerm(search)}>Search</button>
            </div>
          </div>
          <div className="dlg-list">
            <table>
              <thead><tr><th /><th>Invoice</th><th>Document</th><th>Customer</th><th>Co.</th><th>Amount</th><th>Invoice date</th></tr></thead>
              <tbody>
                {(choices.data ?? []).map((c) => (
                  <tr key={c.id} className={bsid === c.id ? "picked" : undefined} onClick={() => pick(c)} style={{ cursor: "pointer" }}>
                    <td><input type="radio" name="bsid" aria-label={`Select BSID ${c.belnr}`} checked={bsid === c.id} onChange={() => {}} /></td>{/* the row click (which a click on the radio also reaches) does the picking */}
                    <td className="font-mono">{c.xblnr ?? "—"}{c.selected ? " ✓" : ""}</td>
                    <td className="font-mono">{c.belnr}/{c.gjahr}/{c.buzei}</td>
                    <td>{c.customer_name ?? c.kunnr}</td>
                    <td>{c.bukrs}</td>
                    <td>{money(c.amount, c.waers)}</td>
                    <td>{c.bldat ?? "—"}</td>
                  </tr>
                ))}
                {choices.data && choices.data.length === 0 && <tr><td colSpan={7} className="text-muted">No open items found.</td></tr>}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted" style={{ marginTop: 8 }}>After saving, the record is matched and scored again with the normal rules. The result (and so the decision) may change. SAP data is never changed.</p>
        </>
      )}
    </Shell>
  );
}

/**
 * All actions of the Action Queue and the Record Detail. `start(action, rows)` opens the right dialog;
 * `dialog` must be rendered by the screen. Stale versions (409) and refusals are shown in the dialog and as a toast.
 */
export function useActions(onDone?: () => void) {
  const toast = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState<{ action: ActionCode; rows: WorkItemRow[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const refresh = () => ["workItems", "workItem", "kpis", "exported", "audit"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const close = () => {
    setOpen(null);
    setError(null);
  };
  const submit: Submit = async (go) => {
    setBusy(true);
    setError(null);
    try {
      const message = await go();
      toast(message, "success");
      close();
      refresh();
      onDone?.();
    } catch (e) {
      const err = e instanceof Error ? e : new Error("The action failed.");
      setError(err);
      if (err instanceof ActionError && err.status === 409) {
        toast(err.message, "error");
        refresh(); // the screen now shows what the other person did
      }
    } finally {
      setBusy(false);
    }
  };

  const start = (action: ActionCode, rows: WorkItemRow[]) => {
    if (rows.length === 0) return;
    setError(null);
    setOpen({ action, rows });
  };

  let dialog: ReactNode = null;
  if (open) {
    const common: Common = { ...open, onClose: close, submit, busy, error };
    dialog =
      open.rows.length === 1 && open.action === "REQUEST_CLARIFICATION" ? <ClarifyDialog {...common} /> :
      open.rows.length === 1 && (open.action === "ADD_UPDATE_DETAILS" || open.action === "ADD_BSID_DETAILS") ? <DetailsDialog {...common} /> :
      <CommentDialog {...common} />;
  }
  return { start, dialog };
}
