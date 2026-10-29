import { type DataSource, type ActionCode, NotAvailableError } from "../data";
import { ACTION_LABELS } from "../data/labels";

type Notify = (text: string, kind?: "info" | "success" | "error") => void;

/** Runs an action through the data layer. Actions are built in M09; until then the answer is "available in M09". */
export async function runAction(ds: DataSource, notify: Notify, action: ActionCode, ids: number[]) {
  try {
    const r = await ds.performAction({ action, ids });
    notify(r.message, r.ok ? "success" : "error");
  } catch (e) {
    if (e instanceof NotAvailableError) notify(`${ACTION_LABELS[action]}: ${e.message}`, "info");
    else notify(e instanceof Error ? e.message : "The action failed.", "error");
  }
}

/** The action buttons of a record - only the actions the signed-in role may take (allowed_actions from the API). */
export default function ActionButtons({ actions, onAction }: { actions: ActionCode[]; onAction: (a: ActionCode) => void }) {
  if (actions.length === 0) return <div className="text-muted text-xs">No actions available for your role on this record.</div>;
  return (
    <div className="action-btns">
      {actions.map((a) => (
        <button
          key={a}
          type="button"
          className={`action-btn ${a === "CONFIRM_EXTRACT_EXCEL" ? "action-btn-approve" : a === "REJECT" ? "action-btn-danger" : a === "ESCALATE_TO_SUPERVISOR" ? "action-btn-danger" : "action-btn-primary"}`}
          onClick={() => onAction(a)}
        >
          {a === "CONFIRM_EXTRACT_EXCEL" ? "📥 " : ""}
          {ACTION_LABELS[a]}
        </button>
      ))}
    </div>
  );
}
