import { useQuery } from "@tanstack/react-query";
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LineElement, LinearScale, PointElement, Tooltip } from "chart.js";
import { useMemo, useState } from "react";
import { Bar, Line } from "react-chartjs-2";
import { useAuth } from "../auth/AuthContext";
import FilterBar from "../components/Filters";
import type { Filters, Kpis } from "../data";
import { money } from "../data/labels";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend);

type CardKey = keyof Kpis["cards"];
const CARDS: { key: CardKey; label: string; icon: string; bg: string; fg: string; sub: string; tip: string; status?: string }[] = [
  { key: "total", label: "Total Processed", icon: "📧", bg: "#eff6ff", fg: "#1e40af", sub: "All records", tip: "All records created from received e-mails, including out-of-scope e-mails." },
  { key: "ai", label: "AI Processed", icon: "🤖", bg: "#ecfdf5", fg: "#059669", sub: "Auto-processed by AI", tip: "Records processed automatically without manual intervention.", status: "AUTO_PROCESSED" },
  { key: "manual", label: "Manual Processing", icon: "✋", bg: "#fffbeb", fg: "#d97706", sub: "Pending review or handled by people", tip: "Human-handled records: pending review plus records already worked by people.", status: "PENDING_REVIEW" },
  { key: "duplicates", label: "Duplicates", icon: "♻️", bg: "#f5f3ff", fg: "#7c3aed", sub: "Duplicates detected", tip: "Repeat submissions of a remittance already received or processed.", status: "DUPLICATE" },
  { key: "exceptions", label: "Exceptions", icon: "⚠️", bg: "#fef2f2", fg: "#dc2626", sub: "Requires investigation", tip: "Records where no valid BSID invoice match was found.", status: "EXCEPTION" },
];

const DIMENSIONS = [
  { key: "customer", label: "Customer" },
  { key: "region", label: "Region" },
  { key: "company_code", label: "Company Code" },
  { key: "classification", label: "Classification" },
  { key: "status", label: "Status" },
] as const;

function quarterOf(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return `${y}-Q${Math.ceil(m / 3)}`;
}

export default function Dashboard() {
  const { ds } = useAuth();
  const [filters, setFilters] = useState<Filters>({});
  const [dimension, setDimension] = useState<(typeof DIMENSIONS)[number]["key"]>("customer");
  const [period, setPeriod] = useState<"month" | "quarter">("month");
  const { data, isLoading, error } = useQuery({ queryKey: ["kpis", filters], queryFn: () => ds.kpis(filters) });

  const trend = useMemo(() => {
    if (!data) return [];
    if (period === "month") return data.monthly_trend.map((m) => ({ ...m, label: m.month }));
    const q = new Map<string, { label: string; ai: number; manual: number; duplicates: number; exceptions: number }>();
    for (const m of data.monthly_trend) {
      const k = quarterOf(m.month);
      const cur = q.get(k) ?? { label: k, ai: 0, manual: 0, duplicates: 0, exceptions: 0 };
      cur.ai += m.ai;
      cur.manual += m.manual;
      cur.duplicates += m.duplicates;
      cur.exceptions += m.exceptions;
      q.set(k, cur);
    }
    return [...q.values()];
  }, [data, period]);

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
            <div className="chart-wrap" style={{ height: 260 }}>
              {data && (
                <Line
                  data={{
                    labels: data.performance_stability.map((d) => d.date),
                    datasets: [
                      { label: "Auto-processing rate (%)", data: data.performance_stability.map((d) => (d.auto_rate === null ? null : Math.round(d.auto_rate * 1000) / 10)), borderColor: "#059669", backgroundColor: "#059669", tension: 0.25, yAxisID: "y" },
                      { label: "Average confidence (%)", data: data.performance_stability.map((d) => d.avg_confidence), borderColor: "#2563eb", backgroundColor: "#2563eb", tension: 0.25, yAxisID: "y" },
                    ],
                  }}
                  options={{ maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } }, plugins: { legend: { position: "bottom" } } }}
                />
              )}
            </div>
          </div>
          <div className="chart-card dashboard-chart-card">
            <div className="chart-title-row">
              <h3>📐 Distribution across Dimensions</h3>
              <select className="chart-select" aria-label="Dimension" value={dimension} onChange={(e) => setDimension(e.target.value as typeof dimension)}>
                {DIMENSIONS.map((d) => (
                  <option key={d.key} value={d.key}>{d.label}</option>
                ))}
              </select>
            </div>
            <div className="chart-wrap" style={{ height: 300 }}>
              {data && (
                <Bar
                  data={{ labels: data.distributions[dimension].map((d) => d.label), datasets: [{ label: "Records", data: data.distributions[dimension].map((d) => d.count), backgroundColor: "#3b82f6" }] }}
                  options={{ maintainAspectRatio: false, plugins: { legend: { display: false } } }}
                />
              )}
            </div>
          </div>
        </div>

        <div className="chart-card dashboard-chart-card dashboard-chart-wide">
          <div className="chart-title-row">
            <h3>📈 Processing Trend</h3>
            <select className="chart-select" aria-label="Period" value={period} onChange={(e) => setPeriod(e.target.value as typeof period)}>
              <option value="month">Month</option>
              <option value="quarter">Quarter</option>
            </select>
          </div>
          <div className="chart-wrap" style={{ height: 280 }}>
            {data && (
              <Bar
                data={{
                  labels: trend.map((t) => t.label),
                  datasets: [
                    { label: "AI processed", data: trend.map((t) => t.ai), backgroundColor: "#059669" },
                    { label: "Manual", data: trend.map((t) => t.manual), backgroundColor: "#d97706" },
                    { label: "Duplicates", data: trend.map((t) => t.duplicates), backgroundColor: "#7c3aed" },
                    { label: "Exceptions", data: trend.map((t) => t.exceptions), backgroundColor: "#dc2626" },
                  ],
                }}
                options={{ maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } }, plugins: { legend: { position: "bottom" } } }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
