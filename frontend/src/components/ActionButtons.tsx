import { useAuth } from "../auth/AuthContext";
import type { ActionCode } from "../data";
import { ACTION_LABELS } from "../data/labels";
import { NEEDS_LIVE_SYSTEM } from "../data/permissions";

/** The action buttons of a record - only the actions the signed-in role may take (allowed_actions from the API). */
export default function ActionButtons({ actions, onAction }: { actions: ActionCode[]; onAction: (a: ActionCode) => void }) {
  const { ds } = useAuth();
  if (actions.length === 0) return <div className="text-muted text-xs">No actions available for your role on this record.</div>;
  return (
    <div className="action-btns">
      {actions.map((a) => (
        <button
          key={a}
          type="button"
          className={`action-btn ${a === "CONFIRM_ADD_EXCEL" ? "action-btn-approve" : a === "REJECT" ? "action-btn-danger" : a === "ESCALATE_TO_SUPERVISOR" ? "action-btn-danger" : "action-btn-primary"}`}
          onClick={() => onAction(a)}
          disabled={ds.kind === "snapshot" && NEEDS_LIVE_SYSTEM.includes(a)}
          title={ds.kind === "snapshot" && NEEDS_LIVE_SYSTEM.includes(a) ? "Needs the live system: this action matches and scores the record again." : undefined}
        >
          {a === "CONFIRM_ADD_EXCEL" ? "📥 " : ""}
          {ACTION_LABELS[a]}
        </button>
      ))}
    </div>
  );
}
