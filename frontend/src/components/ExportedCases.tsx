/** "Exported cases (n)": placeholder until M09 (the Excel-look list of all confirmed cases with "Download .xlsx"). */
export default function ExportedCases({ count, onClose }: { count: number; onClose: () => void }) {
  return (
    <div className="modal-overlay open" style={{ display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div className="modal-panel" role="dialog" aria-label="Exported cases" style={{ height: "auto", width: 520, borderRadius: 10 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📗 Exported cases ({count})</h2>
          <button className="modal-close" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <p>This will list all confirmed cases in an Excel-style view, with a <strong>Download .xlsx</strong> button for all of them.</p>
          <p className="text-muted text-xs" style={{ marginTop: 10 }}>Available with module M09 - confirming a case ("Confirm &amp; Add to Excel") is not active yet, so the list is empty.</p>
        </div>
      </div>
    </div>
  );
}
