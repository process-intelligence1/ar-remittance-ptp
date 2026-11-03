import { ActionError, type ActionCode, type ActionOutcome, type AuditRow, type BulkOutcome, type BulkRequest, type DemoUser, type ActionRequest } from "../types";
import { COMMENT_REQUIRED, NEEDS_LIVE_SYSTEM, STATUS_AFTER, allowedActions } from "../permissions";
import type { SnapRow } from "./rows";

// The analyst actions of the demo edition, applied to the rows in the browser. The rules are those of backend/app/actions.py:
// the row version must match (409), the action must be allowed for the role (403), comment / completeness (422), one audit entry
// with before / after, bulk is all or nothing. SAP data is not touched (there is none). Actions that match and score again
// (Add / Update details, Add BSID details, Mark as Non-Duplicate) need the matching engine and are not available here.

export const STALE = "This record was changed by someone else - refresh and try again.";

export function snapshotOf(r: SnapRow): Record<string, unknown> {
  return {
    decision: r.decision, status: r.status, confidence_score: r.confidence, match_level: r.match_level, kunnr: r.kunnr, bukrs: r.company_code,
    invoice_ref_raw: r.invoice_ref, amount: r.amount, currency: r.currency, payment_date: r.export.payment_date, assigned_role: r.assigned_role,
  };
}

export function confirmProblems(r: SnapRow): string[] {
  const p: string[] = [];
  if (!r.export.invoice_ref_norm && !r.invoice_ref) p.push("invoice number missing");
  if (!r.kunnr) p.push("customer not identified");
  if (!r.bsid_match && r.amount === null) p.push("needs a BSID match or an amount");
  return p;
}

export const actionsFor = (user: DemoUser, r: SnapRow): ActionCode[] => allowedActions(user.role, r.decision, r.status, r.assigned_role, r.resolved);

/** Why this action cannot be done (status code + message), or null. */
export function check(user: DemoUser, r: SnapRow, action: ActionCode, version: number | null | undefined, comment?: string): ActionError | null {
  if (version === null || version === undefined || r.version !== version) return new ActionError(STALE, 409);
  if (NEEDS_LIVE_SYSTEM.includes(action)) return new ActionError("This action matches and scores the record again - it needs the live system, not the demo edition.", 422);
  if (!actionsFor(user, r).includes(action)) return new ActionError(`${action} is not available for this record and role.`, 403);
  if (COMMENT_REQUIRED.includes(action) && !(comment ?? "").trim()) return new ActionError("A comment is required for this action.", 422);
  if (action === "CONFIRM_ADD_EXCEL") {
    const p = confirmProblems(r);
    if (p.length) return new ActionError(`Cannot confirm: ${p.join(", ")}.`, 422);
  }
  return null;
}

export interface Ctx {
  user: DemoUser;
  businessDate: string;
  nextAuditId: () => number;
  pushAudit: (a: AuditRow) => void;
}

/** Applies one action (already checked). Mutates the row; returns the audit entry. */
export function apply(ctx: Ctx, r: SnapRow, req: ActionRequest): AuditRow {
  const before = snapshotOf(r);
  const now = new Date().toISOString();
  const comment = (req.comment ?? "").trim() || null;
  r.status = STATUS_AFTER[req.action] ?? r.status;
  r.action_comment = comment;
  if (req.action === "ESCALATE_TO_SUPERVISOR") r.assigned_role = "AR_SUPERVISOR";
  if (["CONFIRM_ADD_EXCEL", "REJECT", "CLOSE_AS_DUPLICATE"].includes(req.action)) r.resolved = true;
  if (req.action === "CONFIRM_ADD_EXCEL") {
    r.confirmed_by = ctx.user.email;
    r.confirmed_at = now;
  }
  r.version += 1;
  r.updated_at = now;
  const extra: Record<string, unknown> = req.action === "REQUEST_CLARIFICATION"
    ? { subject: req.email?.subject, preview_only: true, note: "Demo edition: nothing was sent." } : {};
  const entry: AuditRow = {
    id: ctx.nextAuditId(), occurred_at: now, business_date: ctx.businessDate, actor: ctx.user.email, actor_role: ctx.user.role,
    entity_type: "work_item", entity_id: r.entry_id, action: req.action, details: { before, after: snapshotOf(r), comment, ...extra },
  };
  ctx.pushAudit(entry);
  return entry;
}

export function performOne(ctx: Ctx, r: SnapRow, req: ActionRequest, toRow: (r: SnapRow) => ActionOutcome["item"]): ActionOutcome {
  const err = check(ctx.user, r, req.action, req.version, req.comment);
  if (err) throw err;
  if (req.action === "REQUEST_CLARIFICATION" && (!req.email?.subject.trim() || !req.email?.body.trim())) throw new ActionError("The e-mail needs a subject and a text.", 422);
  apply(ctx, r, req);
  return { item: toRow(r), outbound_id: null, worker_started: null };
}

/** All or nothing: when any selected row is not valid, no row is changed and the problems are listed. */
export function performBulk(ctx: Ctx, rows: SnapRow[], req: BulkRequest, toRow: (r: SnapRow) => ActionOutcome["item"]): BulkOutcome {
  if (!["CONFIRM_ADD_EXCEL", "REJECT", "ESCALATE_TO_SUPERVISOR", "CLOSE_AS_DUPLICATE"].includes(req.action)) {
    throw new ActionError(`${req.action} cannot be done on several records at once.`, 422);
  }
  if (rows.length === 0) throw new ActionError("Select at least one record.", 422);
  const problems = rows.flatMap((r, i) => {
    const err = check(ctx.user, r, req.action, req.items[i].version, req.comment);
    return err ? [{ entry_id: r.entry_id, status: err.status, message: err.message }] : [];
  });
  if (problems.length) {
    const code = problems.every((p) => p.status === 409) ? 409 : 422;
    throw new ActionError(`${problems.length} of ${rows.length} selected records cannot be processed - nothing was changed.`, code, problems);
  }
  rows.forEach((r, i) => apply(ctx, r, { action: req.action, version: req.items[i].version, comment: req.comment }));
  return { done: rows.length, items: rows.map(toRow) };
}
