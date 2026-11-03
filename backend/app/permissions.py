"""Which actions a role may take on a work item (Knowledge Base table); the actions themselves are in app/actions.py.

Actions offered by the row's decision:
  AUTO_PROCESS          Confirm & Add to Excel
  EXCEPTION             Add BSID Invoice Details / Confirm & Add to Excel / Request Clarification / Reject Record
  MANUAL_REVIEW         Add / Update Invoice Details / Confirm & Add to Excel / Request Clarification / Reject Record
  MANUAL_INVESTIGATION  as MANUAL_REVIEW + Escalate to AR Supervisor
  DUPLICATE             Close as Duplicate / Request Clarification / Mark as Non-Duplicate / Add or Update Details
Who may act: the AR Supervisor on every open row (nothing to escalate to, so no Escalate); any other role on rows
assigned to it; the AR Analyst also on any open row (analysts pick up exceptions and duplicates). Closed rows
(confirmed, resolved, rejected, ignored) offer nothing. Confirm & Add to Excel does NOT touch SAP data: the row
becomes CONFIRMED and the Excel file is the posting file.
"""
CONFIRM, EDIT, ADD_BSID, REJECT = "CONFIRM_ADD_EXCEL", "ADD_UPDATE_DETAILS", "ADD_BSID_DETAILS", "REJECT"
CLARIFY, ESCALATE, CLOSE_DUP, NOT_DUP = "REQUEST_CLARIFICATION", "ESCALATE_TO_SUPERVISOR", "CLOSE_AS_DUPLICATE", "MARK_NON_DUPLICATE"

BY_DECISION = {
    "AUTO_PROCESS": [CONFIRM],
    "EXCEPTION": [ADD_BSID, CONFIRM, CLARIFY, REJECT],
    "MANUAL_REVIEW": [EDIT, CONFIRM, CLARIFY, REJECT],
    "MANUAL_INVESTIGATION": [EDIT, CONFIRM, CLARIFY, ESCALATE, REJECT],
    "DUPLICATE": [CLOSE_DUP, CLARIFY, NOT_DUP, EDIT],
}
CLOSED_STATUS = ("CONFIRMED", "RESOLVED", "REJECTED", "IGNORED")
OPEN_WORKFLOW = ("AWAITING_CUSTOMER", "ESCALATED")  # open rows waiting for someone (customer reply / the AR Supervisor)
SUPERVISOR, ANALYST = "AR_SUPERVISOR", "AR_ANALYST"
# Action -> status the row gets (None = decided by the action: re-score, close as duplicate ...)
STATUS_AFTER = {CONFIRM: "CONFIRMED", REJECT: "REJECTED", CLARIFY: "AWAITING_CUSTOMER", ESCALATE: "ESCALATED",
                CLOSE_DUP: "RESOLVED"}


def allowed_actions(role: str, decision: str | None, status: str, assigned_role: str | None,
                    resolved: bool = False) -> list[str]:
    if resolved or status in CLOSED_STATUS or decision not in BY_DECISION:
        return []
    if decision == "AUTO_PROCESS" and status not in ("AUTO_PROCESSED", *OPEN_WORKFLOW):
        return []  # e.g. a high score sent to review because an attachment was unreadable
    actions = BY_DECISION[decision]
    if status == "ESCALATED":  # handed to the AR Supervisor: only the supervisor acts, and cannot escalate further
        return [a for a in actions if a != ESCALATE] if role == SUPERVISOR else []
    if role == SUPERVISOR:
        return [a for a in actions if a != ESCALATE]
    if role == ANALYST or assigned_role == role:
        return list(actions)
    return []
