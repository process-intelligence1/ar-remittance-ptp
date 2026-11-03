import { bucketOf, buildCharts, type ChartRow } from "../charts";
import type { Filters, Kpis } from "../types";
import { applyFilters, dayOf, type SnapRow } from "./rows";

// The Dashboard numbers, computed in the browser from the rows. Same rules as GET /api/kpis (backend/app/api/dashboard.py);
// frontend/src/test/snapshot.test.ts checks the result against what the real API answered for the same data.
// Money is added in whole cents so the sums are exact.

const cents = (x: number | null) => (x === null ? 0 : Math.round(x * 100));
const money = (c: number) => Math.round(c) / 100;
/** Rounds the exact binary value like Python's round() does (toFixed does), so a .5 that is really .4999... rounds down in both. */
const round = (x: number, places: number) => Number(x.toFixed(places));

type Bucket = "total" | "ai" | "manual" | "duplicates" | "exceptions";
const CARD_KEYS: Bucket[] = ["total", "ai", "manual", "duplicates", "exceptions"];
const TOP_CUSTOMERS = 10;

function cardBucket(decision: string | null): string {
  const b = bucketOf(decision);
  return b === "auto" ? "ai" : b ?? "other";
}

/** The date a row's money is dated at: the payment date, else the day the e-mail arrived. */
const rowDate = (r: SnapRow) => r.export.payment_date ?? dayOf(r.received_at);
/** The date in the trend chart: the e-mail's own business date for history e-mails, else the day it arrived. */
const trendDay = (r: SnapRow) => (r.export.source === "history" && r.export.email_business_date ? r.export.email_business_date : dayOf(r.received_at));

export function computeKpis(allRows: SnapRow[], filters: Filters = {}): Kpis {
  const rows = applyFilters(allRows, filters);
  const cards = Object.fromEntries(CARD_KEYS.map((k) => [k, { count: 0, cents: 0 }])) as Record<Bucket, { count: number; cents: number }>;
  const dims: Record<string, Map<string, { count: number; cents: number }>> = {
    customer: new Map(), region: new Map(), company_code: new Map(), classification: new Map(), status: new Map(),
  };
  const months = new Map<string, { total: number; ai: number; manual: number; duplicates: number; exceptions: number }>();
  const days = new Map<string, { rows: number; ai: number; conf: number; confN: number }>();
  let unconverted = 0;
  const missing = new Map<string, number>();
  const chartRows: ChartRow[] = [];

  for (const r of rows) {
    const c = r.usd_status === "OK" ? cents(r.amount_usd) : null;
    if (r.usd_status !== "OK" && r.usd_status !== "NO_AMOUNT") {
      unconverted += 1;
      missing.set(r.currency ?? "", (missing.get(r.currency ?? "") ?? 0) + 1);
    }
    const b = cardBucket(r.decision);
    chartRows.push({ decision: r.decision, classification: r.classification, customer: r.customer_name, region: r.region, company_code: r.company_code, day: trendDay(r) });
    for (const k of ["total", ...(CARD_KEYS.includes(b as Bucket) ? [b] : [])] as Bucket[]) {
      cards[k].count += 1;
      if (c !== null) cards[k].cents += c;
    }
    const values: Record<string, string> = {
      customer: r.customer_name || "(unidentified)", region: r.region || "(none)", company_code: r.company_code || "(none)",
      classification: r.classification, status: r.status,
    };
    for (const [dim, v] of Object.entries(values)) {
      const g = dims[dim].get(v) ?? { count: 0, cents: 0 };
      g.count += 1;
      if (c !== null) g.cents += c;
      dims[dim].set(v, g);
    }
    const on = rowDate(r);
    if (on) {
      const key = on.slice(0, 7);
      const m = months.get(key) ?? { total: 0, ai: 0, manual: 0, duplicates: 0, exceptions: 0 };
      m.total += 1;
      if (b in m) m[b as keyof typeof m] += 1;
      months.set(key, m);
      const d = days.get(on) ?? { rows: 0, ai: 0, conf: 0, confN: 0 };
      d.rows += 1;
      d.ai += b === "ai" ? 1 : 0;
      if (r.confidence !== null) {
        d.conf += Math.round(r.confidence * 100);
        d.confN += 1;
      }
      days.set(on, d);
    }
  }

  const dist = (name: string, top?: number) => {
    const all = [...dims[name].entries()].sort((a, b) => b[1].count - a[1].count || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
      .map(([label, v]) => ({ label, count: v.count, usd: money(v.cents) }));
    if (top && all.length > top) {
      const rest = all.slice(top);
      return [...all.slice(0, top), { label: "Other", count: rest.reduce((s, x) => s + x.count, 0), usd: round(rest.reduce((s, x) => s + x.usd, 0), 2) }];
    }
    return all;
  };

  return {
    cards: Object.fromEntries(CARD_KEYS.map((k) => [k, { count: cards[k].count, usd: money(cards[k].cents) }])) as Kpis["cards"],
    usd: { unconverted, missing_rate_currencies: Object.fromEntries(missing), note: "Rows without an exchange rate are not included in USD sums." },
    distributions: { customer: dist("customer", TOP_CUSTOMERS), region: dist("region"), company_code: dist("company_code"), classification: dist("classification"), status: dist("status") },
    monthly_trend: [...months.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([month, v]) => ({ month, ...v })),
    charts: buildCharts(chartRows),
    performance_stability: [...days.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([date, v]) => ({
      date, rows: v.rows, auto_rate: v.rows ? round(v.ai / v.rows, 4) : null, avg_confidence: v.confN ? round(v.conf / (100 * v.confN), 2) : null,
    })),
  };
}
