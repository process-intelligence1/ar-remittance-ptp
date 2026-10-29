export default function DemoControl() {
  return (
    <div className="page active" id="page-demo">
      <div className="page-content">
        <div className="page-header">
          <h1>🎛️ Demo Control</h1>
          <p>Controls for presenters - coming in a later module</p>
        </div>
        <div className="table-card" style={{ padding: 20 }}>
          <p>This page will let a presenter:</p>
          <ul style={{ margin: "8px 0 0 18px", lineHeight: 1.8 }}>
            <li>reset the demo to its saved starting point,</li>
            <li>send a sample e-mail into the inbox,</li>
            <li>move the demo business date,</li>
            <li>start a processing run right away ("Process now").</li>
          </ul>
          <p className="text-muted text-xs" style={{ marginTop: 12 }}>Nothing here is active yet (module M11).</p>
        </div>
      </div>
    </div>
  );
}
