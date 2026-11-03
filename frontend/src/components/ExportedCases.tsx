import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { COLUMNS, SUMMARY_HEADERS, downloadWorkbook, fileName, summarise, summaryCells } from "../export/cases";
import { useToast } from "./Toasts";

const letter = (i: number) => {
  let s = "";
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
};

function show(v: unknown, kind?: string): string {
  if (v === null || v === undefined || v === "") return "";
  if (v instanceof Date) return kind === "date" ? v.toISOString().slice(0, 10) : v.toISOString().slice(0, 16).replace("T", " ");
  if (typeof v === "number") return kind === "percent" ? v.toFixed(1) : v.toLocaleString("en-US", { minimumFractionDigits: kind === "number" ? 2 : 0, maximumFractionDigits: 3 });
  return String(v);
}

/** "Exported cases (n)": an Excel-look view of ALL confirmed cases (sheets "Cases" and "Summary") with "Download .xlsx". */
export default function ExportedCases({ onClose }: { onClose: () => void }) {
  const { ds } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [sheet, setSheet] = useState<"Cases" | "Summary">("Cases");
  const [busy, setBusy] = useState(false);
  const q = useQuery({ queryKey: ["exported"], queryFn: () => ds.exportedCases() });
  const items = q.data?.items ?? [];
  const summary = summarise(items);

  const download = async () => {
    setBusy(true);
    try {
      await downloadWorkbook(items);
      const n = await ds.markExported(items.map((i) => i.entry_id));
      toast(`${fileName()} downloaded - ${n} case(s) marked as exported.`, "success");
      qc.invalidateQueries({ queryKey: ["exported"] });
      qc.invalidateQueries({ queryKey: ["workItems"] });
    } catch (e) {
      toast(e instanceof Error ? e.message : "The download failed.", "error");
    } finally {
      setBusy(false);
    }
  };

  const heads = sheet === "Cases" ? COLUMNS.map((c) => c.header) : SUMMARY_HEADERS;
  const rows: { cells: unknown[]; kinds: (string | undefined)[] }[] =
    sheet === "Cases"
      ? items.map((c) => ({ cells: COLUMNS.map((col) => col.get(c)), kinds: COLUMNS.map((col) => col.kind) }))
      : summary.map((s) => ({ cells: summaryCells(s), kinds: [undefined, undefined, undefined, "count", "number", "number", "number"] }));

  return (
    <div className="dlg-overlay" onClick={onClose}>
      <div className="xl" role="dialog" aria-label="Exported cases" onClick={(e) => e.stopPropagation()}>
        <div className="xl-title">
          <span>📗 {fileName()} — Exported cases ({q.data?.count ?? 0})</span>
          <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button type="button" onClick={download} disabled={busy || items.length === 0}>{busy ? "Preparing…" : "⬇ Download .xlsx"}</button>
            <button type="button" className="xl-close" aria-label="Close" onClick={onClose}>✕</button>
          </span>
        </div>
        <div className="xl-sheet">
          {q.isLoading && <div className="xl-empty">Loading…</div>}
          {q.error && <div className="xl-empty">Could not load the confirmed cases: {(q.error as Error).message}</div>}
          {q.data && items.length === 0 && (
            <div className="xl-empty">No confirmed cases yet. Use “Confirm &amp; Add to Excel” on a record and it appears here.</div>
          )}
          {q.data && items.length > 0 && (
            <table aria-label={`Sheet ${sheet}`}>
              <thead>
                <tr>
                  <th className="xl-corner" />
                  {heads.map((_, i) => <th key={i}>{letter(i)}</th>)}
                </tr>
                <tr className="xl-heads">
                  <th className="xl-rownum xl-corner">1</th>
                  {heads.map((h) => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td className="xl-rownum">{i + 2}</td>
                    {r.cells.map((v, j) => (
                      <td key={j} className={typeof v === "number" ? "num" : undefined}>{show(v, r.kinds[j])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="xl-tabs" role="tablist">
          {(["Cases", "Summary"] as const).map((s) => (
            <button key={s} type="button" role="tab" aria-selected={sheet === s} className={sheet === s ? "active" : ""} onClick={() => setSheet(s)}>{s}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
