import { describe, expect, it } from "vitest";
import fixture from "../../../data/eval/dashboard_charts_fixture.json";
import { buildCharts, bucketOf, periodKey, type ChartRow } from "../data/charts";

describe("chart data (shared fixture with the backend)", () => {
  it("gives exactly the numbers the backend gives for the same rows", () => {
    expect(buildCharts(fixture.rows as ChartRow[])).toEqual(fixture.expected);
  });

  it("uses ISO weeks, calendar months and quarters", () => {
    expect(periodKey("2026-12-30", "week").key).toBe("2026-W53");
    expect(periodKey("2027-01-03", "week").key).toBe("2026-W53");
    expect(periodKey("2027-01-04", "week").key).toBe("2027-W01");
    expect(periodKey("2026-03-31", "quarter")).toEqual({ key: "2026-Q1", label: "2026 Q1" });
    expect(periodKey("2026-04-01", "quarter").key).toBe("2026-Q2");
  });

  it("follows the decision only (actions never move a row) and ignores out-of-scope rows", () => {
    expect(["AUTO_PROCESS", "MANUAL_REVIEW", "MANUAL_INVESTIGATION", "EXCEPTION", "DUPLICATE"].map(bucketOf)).toEqual([
      "auto", "manual", "manual", "exceptions", "duplicates",
    ]);
    expect(bucketOf("OUT_OF_SCOPE")).toBeNull();
    expect(bucketOf(null)).toBeNull();
  });

  it("leaves duplicates out of Performance Stability and rows without a value out of a dimension", () => {
    const c = buildCharts([{ decision: "DUPLICATE", classification: "DUPLICATE", customer: "A", region: null, company_code: "1000", day: "2026-01-01" }]);
    expect(c.performance.every((p) => p.total === 0)).toBe(true);
    expect(c.dimensions.region).toEqual([]);
    expect(c.dimensions.customer[0].duplicates).toBe(1);
  });
});
