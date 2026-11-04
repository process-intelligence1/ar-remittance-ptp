import { useQuery } from "@tanstack/react-query";
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LineElement, LinearScale, PointElement, Tooltip, type Plugin } from "chart.js";
import { useMemo, useState } from "react";
import { Bar, Line } from "react-chartjs-2";
import { useAuth } from "../auth/AuthContext";
import FilterBar from "../components/Filters";
import type { ChartDimension, Filters, Kpis, TrendPeriod } from "../data";
import { money } from "../data/labels";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend);

export const COLORS = { auto: "#059669", manual: "#d97706", duplicates: "#7c3aed", exceptions: "#dc2626", remittance: "#3b82f6", ptp: "#ea580c" } as const;

type CardKey = keyof Kpis["cards"];
const CARDS: { key: CardKey; label: string; icon: string; bg: string; fg: string; sub: string; tip: string; status?: string }[] = [
  { key: "total", label: "Total Processed", icon: "📧", bg: "#eff6ff", fg: "#1e40af", sub: "All records", tip: "All records created from received e-mails, including out-of-scope e-mails." },
  { key: "ai", label: "Auto Processed", icon: "🤖", bg: "#ecfdf5", fg: "#059669", sub: "Processed automatically", tip: "Records processed automatically without manual intervention.", status: "AUTO_PROCESSED" },
  { key: "manual", label: "Manual Processing", icon: "✋", bg: "#fffbeb", fg: "#d97706", sub: "Pending review or handled by people", tip: "Human-handled records: pending review plus records already worked by people.", status: "PENDING_REVIEW" },
  { key: "duplicates", label: "Duplicates", icon: "♻️", bg: "#f5f3ff", fg: "#7c3aed", sub: "Duplicates detected", tip: "Repeat submissions of a remittance already received or processed.", status: "DUPLICATE" },
  { key: "exceptions", label: "Exceptions", icon: "⚠️", bg: "#fef2f2", fg: "#dc2626", sub: "Requires investigation", tip: "Records where no valid BSID invoice match was found.", status: "EXCEPTION" },
];

const DIMENSIONS: { key: ChartDimension; label: string }[] = [
  { key: "customer", label: "Customer" },
  { key: "region", label: "Region" },
  { key: "company_code", label: "Company Code" },
];
const PERIODS: { key: TrendPeriod; label: string }[] = [
  { key: "date", label: "Date" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "quarter", label: "Quarter" },
];

/** Writes "count (pct%)" into every segment of the horizontal Performance Stability bars (pct of the classification). */
export function performanceLabels(totals: number[]): Plugin<"bar"> {
  return {
    id: "performanceLabels",
    afterDatasetsDraw(chart) {
      const ctx = chart.ctx;
      ctx.save();
      ctx.font = "bold 10px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      chart.data.datasets.forEach((ds, i) => {
        chart.getDatasetMeta(i).data.forEach((bar, j) => {
          const value = Number(ds.data[j] ?? 0);
          if (!value) return;
          const { x, base, y } = bar.getProps(["x", "base", "y"], true) as { x: number; base: number; y: number };
          const text = `${value} (${Math.round((value / (totals[j] || 1)) * 100)}%)`;
          if (Math.abs(x - base) >= ctx.measureText(text).width + 6) ctx.fillText(text, (x + base) / 2, y);
        });
      });
      ctx.restore();
    },
  };
}

/** Slimmer bars for the Distribution chart (half of the space between two categories stays free; never wider than 44 px). */
const SLIM = { barPercentage: 0.55, categoryPercentage: 0.8, maxBarThickness: 44 } as const;

/** The key of the Distribution chart. It is HTML (not Chart.js' own legend) so it stays visible while the wide chart scrolls sideways. */
export function DistributionLegend() {
  const items = [["Auto Processed", COLORS.auto], ["Manual Processing", COLORS.manual], ["Duplicates", COLORS.duplicates], ["Exceptions", COLORS.exceptions]] as const;
  return (
    <div className="chart-legend" data-testid="distribution-legend" style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "2px 0 8px 2px", fontSize: 12, color: "var(--c-text2)" }}>
      {items.map(([label, colour]) => (
        <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span aria-hidden="true" style={{ width: 12, height: 12, borderRadius: 3, background: colour, display: "inline-block" }} />
          {label}
        </span>
      ))}
    </div>
  );
}

/** Writes the count into every segment of the vertical stacked bars of the Distribution chart. */
export const stackLabels: Plugin<"bar"> = {
  id: "stackLabels",
  afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    ctx.save();
    ctx.font = "bold 10px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    chart.data.datasets.forEach((ds, i) => {
      chart.getDatasetMeta(i).data.forEach((bar, j) => {
        const value = Number(ds.data[j] ?? 0);
        if (!value) return;
        const { x, y, base } = bar.getProps(["x", "y", "base"], true) as { x: number; y: number; base: number };
        if (Math.abs(base - y) >= 13) ctx.fillText(String(value), x, (y + base) / 2);
      });
    });
    ctx.restore();
  },
};

export default function Dashboard() {
  const { ds } = useAuth();
  const [filters, setFilters] = useState<Filters>({});
  const [dimension, setDimension] = useState<ChartDimension>("customer");
  const [period, setPeriod] = useState<TrendPeriod>("month");
  const { data, isLoading, error } = useQuery({ queryKey: ["kpis", filters], queryFn: () => ds.kpis(filters) });

  // During a roll-out the API can still be the old version without chart data: show a note instead of crashing.
  const charts = data?.charts?.performance && data.charts.dimensions && data.charts.trend ? data.charts : null;
  const perfPlugin = useMemo(() => performanceLabels((charts?.performance ?? []).map((p) => p.total)), [data]);
  const dimPoints = charts?.dimensions[dimension] ?? [];
  const trend = charts?.trend[period] ?? [];
  const pct = (s: { total: number; auto: number }) => (s.total ? Math.round((s.auto / s.total) * 1000) / 10 : 0);

  if (error) return <div className="page active"><div className="page-content"><div className="empty-state">Could not load the dashboard: {(error as Error).message}</div></div></div>;

  return (
    <div className="page active" id="page-dashboard">
      <div className="page-content">
        <FilterBar value={filters} onChange={setFilters} extra="dashboard" />
        <div className="kpi-grid" id="kpi-grid">
          {CARDS.map((c) => {
            const card = data?.cards[c.key];
            const active = c.status && filters.status === c.status;
            return (
              <div
                key={c.key}
                className="kpi-card filterable"
                style={active ? { outline: "2px solid var(--c-primary)" } : undefined}
                title={c.status ? "Click to filter by this status" : "Click to clear the status filter"}
                onClick={() => setFilters((f) => ({ ...f, status: active || !c.status ? undefined : c.status }))}
              >
                <div className="kpi-header">
                  <span className="kpi-label">
                    {c.label} <span className="kpi-info" data-tooltip={c.tip}>ⓘ</span>
                  </span>
                  <div className="kpi-icon" style={{ background: c.bg, color: c.fg }}>{c.icon}</div>
                </div>
                <div className="kpi-value" data-testid={`kpi-${c.key}`}>{isLoading || !card ? "—" : card.count.toLocaleString("en-US")}</div>
                <div className="kpi-sub">
                  {c.sub}
                  {card && card.usd !== null ? ` · ${money(card.usd)} USD` : ""}
                </div>
              </div>
            );
          })}
        </div>
        {data && data.usd.unconverted > 0 && (
          <p className="usd-flag" role="note">
            {data.usd.unconverted} record(s) have no exchange rate ({Object.keys(data.usd.missing_rate_currencies).join(", ")}) and are not included in the USD amounts.
          </p>
        )}

        <div className="dashboard-chart-row dashboard-chart-row-top">
          <div className="chart-card dashboard-chart-card">
            <h3>📊 Performance Stability</h3>
            <div className="chart-wrap" style={{ height: 260 }} data-testid="chart-performance">
              {data && !charts && <div className="empty-state" data-testid="chart-unavailable">Chart data unavailable</div>}
              {charts && (
                <Bar
                  plugins={[perfPlugin]}
                  data={{
                    labels: charts.performance.map((p) => p.label),
                    datasets: [
                      { label: "Auto Processed", data: charts.performance.map((p) => p.auto), backgroundColor: COLORS.auto, borderRadius: 3 },
                      { label: "Manual Processing", data: charts.performance.map((p) => p.manual), backgroundColor: COLORS.manual, borderRadius: 3 },
                      { label: "Exceptions", data: charts.performance.map((p) => p.exceptions), backgroundColor: COLORS.exceptions, borderRadius: 3 },
                    ],
                  }}
                  options={{
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: "bottom", labels: { font: { size: 10 }, padding: 8 } } },
                    scales: {
                      x: { stacked: true, beginAtZero: true, title: { display: true, text: "Number of Emails", font: { size: 10, weight: "bold" } }, ticks: { font: { size: 9 } } },
                      y: { stacked: true, title: { display: true, text: "Classification", font: { size: 10, weight: "bold" } }, ticks: { font: { size: 9 } } },
                    },
                  }}
                />
              )}
            </div>
          </div>

          <div className="chart-card dashboard-chart-card">
            <div className="chart-title-row">
              <h3>📐 Distribution across Dimensions</h3>
              <select className="chart-select" aria-label="Dimension" value={dimension} onChange={(e) => setDimension(e.target.value as ChartDimension)}>
                {DIMENSIONS.map((d) => (
                  <option key={d.key} value={d.key}>{d.label}</option>
                ))}
              </select>
            </div>
            {charts && <DistributionLegend />}
            <div className="chart-wrap dimension-scroll-wrap" style={{ height: 320, overflowX: "auto", overflowY: "hidden" }} data-testid="chart-dimension">
              {data && !charts && <div className="empty-state" data-testid="chart-unavailable">Chart data unavailable</div>}
              {charts && (
                <div style={{ height: 300, width: `max(100%, ${Math.max(500, dimPoints.length * 120)}px)` }}>
                  <Bar
                    plugins={[stackLabels]}
                    data={{
                      labels: dimPoints.map((d) => d.label),
                      datasets: [
                        { label: "Auto Processed", data: dimPoints.map((d) => d.auto), backgroundColor: COLORS.auto, borderRadius: 3, ...SLIM },
                        { label: "Manual Processing", data: dimPoints.map((d) => d.manual), backgroundColor: COLORS.manual, borderRadius: 3, ...SLIM },
                        { label: "Duplicates", data: dimPoints.map((d) => d.duplicates), backgroundColor: COLORS.duplicates, borderRadius: 3, ...SLIM },
                        { label: "Exceptions", data: dimPoints.map((d) => d.exceptions), backgroundColor: COLORS.exceptions, borderRadius: 3, ...SLIM },
                      ],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: { legend: { display: false } }, // the legend above the chart stays in view while the chart scrolls sideways
                      scales: {
                        x: { stacked: true, title: { display: true, text: DIMENSIONS.find((d) => d.key === dimension)!.label, font: { size: 10, weight: "bold" } }, ticks: { font: { size: 9 }, maxRotation: 35, minRotation: 0 } },
                        y: { stacked: true, beginAtZero: true, title: { display: true, text: "Email Count", font: { size: 10, weight: "bold" } }, ticks: { font: { size: 9 } } },
                      },
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="chart-card dashboard-chart-card dashboard-chart-wide">
          <div className="chart-title-row">
            <h3>📈 Monthly Processing Trend</h3>
            <select className="chart-select" aria-label="Period" value={period} onChange={(e) => setPeriod(e.target.value as TrendPeriod)}>
              {PERIODS.map((p) => (
                <option key={p.key} value={p.key}>{p.label}</option>
              ))}
            </select>
          </div>
          <div className="chart-wrap" style={{ height: 280 }} data-testid="chart-trend">
            {data && !charts && <div className="empty-state" data-testid="chart-unavailable">Chart data unavailable</div>}
              {charts && (
              <Line
                data={{
                  labels: trend.map((t) => t.label),
                  datasets: [
                    { label: "Remittance AI Processed %", data: trend.map((t) => pct(t.remittance)), borderColor: COLORS.remittance, backgroundColor: "rgba(59,130,246,0.15)", tension: 0.25, pointRadius: 3 },
                    { label: "PTP AI Processed %", data: trend.map((t) => pct(t.ptp)), borderColor: COLORS.ptp, backgroundColor: "rgba(234,88,12,0.15)", tension: 0.25, pointRadius: 3 },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { position: "bottom", labels: { font: { size: 10 }, padding: 8 } } },
                  scales: {
                    x: { title: { display: true, text: PERIODS.find((p) => p.key === period)!.label, font: { size: 10, weight: "bold" } }, ticks: { font: { size: 9 }, maxRotation: 45 } },
                    y: { beginAtZero: true, max: 100, title: { display: true, text: "AI Processed (%)", font: { size: 10, weight: "bold" } }, ticks: { font: { size: 9 }, callback: (v) => `${v}%` } },
                  },
                }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
