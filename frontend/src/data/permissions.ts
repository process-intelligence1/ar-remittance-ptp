import type { ActionCode, Role } from "./types";

// The same rules as backend/app/permissions.py (Knowledge Base table). Used by the demo edition, which has no server to ask.
// Both are tested against one fixture made by the Python code: data/eval/snapshot_rules_fixture.json.

export const BY_DECISION: Record<string, ActionCode[]> = {
  AUTO_PROCESS: ["CONFIRM_ADD_EXCEL"],
  EXCEPTION: ["ADD_BSID_DETAILS", "CONFIRM_ADD_EXCEL", "REQUEST_CLARIFICATION", "REJECT"],
  MANUAL_REVIEW: ["ADD_UPDATE_DETAILS", "CONFIRM_ADD_EXCEL", "REQUEST_CLARIFICATION", "REJECT"],
  MANUAL_INVESTIGATION: ["ADD_UPDATE_DETAILS", "CONFIRM_ADD_EXCEL", "REQUEST_CLARIFICATION", "ESCALATE_TO_SUPERVISOR", "REJECT"],
  DUPLICATE: ["CLOSE_AS_DUPLICATE", "REQUEST_CLARIFICATION", "MARK_NON_DUPLICATE", "ADD_UPDATE_DETAILS"],
};
export const CLOSED_STATUS = ["CONFIRMED", "RESOLVED", "REJECTED", "IGNORED"];
export const OPEN_WORKFLOW = ["AWAITING_CUSTOMER", "ESCALATED"];
/** Action -> the status the row gets */
export const STATUS_AFTER: Partial<Record<ActionCode, string>> = {
  CONFIRM_ADD_EXCEL: "CONFIRMED",
  REJECT: "REJECTED",
  REQUEST_CLARIFICATION: "AWAITING_CUSTOMER",
  ESCALATE_TO_SUPERVISOR: "ESCALATED",
  CLOSE_AS_DUPLICATE: "RESOLVED",
};
/** Actions that match and score the record again. They need the matching engine, which only the live edition has. */
export const NEEDS_LIVE_SYSTEM: ActionCode[] = ["ADD_UPDATE_DETAILS", "ADD_BSID_DETAILS", "MARK_NON_DUPLICATE"];
export const COMMENT_REQUIRED: ActionCode[] = ["REJECT", "ESCALATE_TO_SUPERVISOR"];

export function allowedActions(role: Role | string, decision: string | null, status: string, assignedRole: string | null, resolved = false): ActionCode[] {
  if (resolved || CLOSED_STATUS.includes(status) || !decision || !(decision in BY_DECISION)) return [];
  if (decision === "AUTO_PROCESS" && !["AUTO_PROCESSED", ...OPEN_WORKFLOW].includes(status)) return [];
  const actions = BY_DECISION[decision];
  if (status === "ESCALATED") return role === "AR_SUPERVISOR" ? actions.filter((a) => a !== "ESCALATE_TO_SUPERVISOR") : [];
  if (role === "AR_SUPERVISOR") return actions.filter((a) => a !== "ESCALATE_TO_SUPERVISOR");
  if (role === "AR_ANALYST" || assignedRole === role) return [...actions];
  return [];
}
