import type { ChartsData, ChartDimension, DimensionPoint, PerformancePoint, TrendPeriod, TrendPoint } from "./types";

// Same rules as backend/app/charts.py (shared fixture: data/eval/dashboard_charts_fixture.json). Used by the demo edition,
// which computes the chart data in the browser from the rows - so actions taken in a demo update the Dashboard at once.

export type Bucket = "auto" | "manual" | "duplicates" | "exceptions";

export interface ChartRow {
  status: string;
  resolved_by?: string | null;
  classification: string;
  customer: string | null;
  region: string | null;
  company_code: string | null;
  day: string | null; // YYYY-MM-DD: e-mail received / processing date (business date for history e-mails)
}

const CLASS_LABELS: Record<string, string> = { REMITTANCE: "Remittance", PTP: "Promise-to-Pay" };
const DIMENSIONS: ChartDimension[] = ["customer", "region", "company_code"];
const PERIODS: TrendPeriod[] = ["date", "week", "month", "quarter"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function bucketOf(status: string, resolvedBy?: string | null): Bucket | null {
  if (status === "DUPLICATE") return "duplicates";
  if (status === "EXCEPTION") return "exceptions";
  if (status === "AUTO_PROCESSED" || (status === "RESOLVED" && (resolvedBy || "system") === "system")) return "auto";
  if (["PENDING_REVIEW", "RESOLVED", "REJECTED", "CONFIRMED"].includes(status)) return "manual";
  return null;
}

function parseDay(day: string): { y: number; m: number; d: number; date: Date } {
  const [y, m, d] = day.split("-").map(Number);
  return { y, m, d, date: new Date(Date.UTC(y, m - 1, d)) };
}

/** ISO week (Monday start) of a UTC date. */
function isoWeek(date: Date): { year: number; week: number } {
  const t = new Date(date.getTime());
  const dayNum = (t.getUTCDay() + 6) % 7; // Monday = 0
  t.setUTCDate(t.getUTCDate() - dayNum + 3); // the Thursday of this week decides the year
  const year = t.getUTCFullYear();
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const week = 1 + Math.round(((t.getTime() - jan4.getTime()) / 86400000 - 3 + ((jan4.getUTCDay() + 6) % 7)) / 7);
  return { year, week };
}

export function periodKey(day: string, period: TrendPeriod): { key: string; label: string } {
  const { y, m, d, date } = parseDay(day);
  if (period === "date") return { key: day, label: `${d} ${MONTHS[m - 1]} ${y}` };
  if (period === "week") {
    const w = isoWeek(date);
    const k = `${w.year}-W${String(w.week).padStart(2, "0")}`;
    return { key: k, label: k };
  }
  if (period === "month") return { key: `${y}-${String(m).padStart(2, "0")}`, label: `${MONTHS[m - 1]} ${y}` };
  const q = Math.floor((m - 1) / 3) + 1;
  return { key: `${y}-Q${q}`, label: `${y} Q${q}` };
}

const UNKNOWN = new Set(["unknown", "n/a", "na", "null", "undefined", "-", "—", "(none)", "(unidentified)"]);
const known = (v: string | null): string | null => {
  const s = (v ?? "").trim();
  return !s || UNKNOWN.has(s.toLowerCase()) ? null : s;
};

export function buildCharts(rows: ChartRow[]): ChartsData {
  const perf: Record<string, { auto: number; manual: number; exceptions: number }> = {
    REMITTANCE: { auto: 0, manual: 0, exceptions: 0 },
    PTP: { auto: 0, manual: 0, exceptions: 0 },
  };
  const dims: Record<ChartDimension, Map<string, DimensionPoint>> = { customer: new Map(), region: new Map(), company_code: new Map() };
  const trend: Record<TrendPeriod, Map<string, TrendPoint>> = { date: new Map(), week: new Map(), month: new Map(), quarter: new Map() };

  for (const r of rows) {
    const b = bucketOf(r.status, r.resolved_by);
    if (r.classification in perf && (b === "auto" || b === "manual" || b === "exceptions")) perf[r.classification][b] += 1;
    for (const dim of DIMENSIONS) {
      const v = known(r[dim]);
      if (v === null) continue;
      const g = dims[dim].get(v) ?? { label: v, auto: 0, manual: 0, duplicates: 0, exceptions: 0, total: 0 };
      g.total += 1;
      if (b) g[b] += 1;
      dims[dim].set(v, g);
    }
    if (r.classification in CLASS_LABELS && r.day) {
      for (const p of PERIODS) {
        const { key, label } = periodKey(r.day, p);
        const t = trend[p].get(key) ?? { key, label, remittance: { total: 0, auto: 0 }, ptp: { total: 0, auto: 0 } };
        const side = r.classification === "REMITTANCE" ? t.remittance : t.ptp;
        side.total += 1;
        if (b === "auto") side.auto += 1;
        trend[p].set(key, t);
      }
    }
  }
  const performance: PerformancePoint[] = Object.entries(perf).map(([c, v]) => ({ label: CLASS_LABELS[c], ...v, total: v.auto + v.manual + v.exceptions }));
  const byTotal = (a: DimensionPoint, b: DimensionPoint) => b.total - a.total || (a.label < b.label ? -1 : a.label > b.label ? 1 : 0);
  const sortedTrend = (m: Map<string, TrendPoint>) => [...m.values()].sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  return {
    performance,
    dimensions: { customer: [...dims.customer.values()].sort(byTotal), region: [...dims.region.values()].sort(byTotal), company_code: [...dims.company_code.values()].sort(byTotal) },
    trend: { date: sortedTrend(trend.date), week: sortedTrend(trend.week), month: sortedTrend(trend.month), quarter: sortedTrend(trend.quarter) },
  };
}
