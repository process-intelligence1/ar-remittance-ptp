/* 4 Nov 2026 review changes: the Distribution chart's key and slimmer bars, the promise section of a record, Reset at the top of Demo Control. */
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { detail, fakeDs, renderApp, signedIn } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => cleanup());

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Props = Record<string, any>;
const charts = () => (globalThis as unknown as { __chartProps: Props[] }).__chartProps;

describe("Distribution across Dimensions", () => {
  it("has its own key above the chart (it stays in view while the chart scrolls sideways) and slim bars", async () => {
    signedIn();
    renderApp(fakeDs(), "#/");
    await screen.findByTestId("kpi-total");
    const legend = screen.getByTestId("distribution-legend");
    expect([...legend.children].map((c) => c.textContent)).toEqual(["Auto Processed", "Manual Processing", "Duplicates", "Exceptions"]);
    expect(screen.getByTestId("chart-dimension").contains(legend)).toBe(false); // outside the scrolling area
    const c = [...charts()].reverse().find((p) => p.kind === "bar" && p.options?.indexAxis !== "y")!;
    expect(c.options.plugins.legend.display).toBe(false); // no second, hidden legend inside the wide canvas
    for (const ds of c.data.datasets) {
      expect(ds.barPercentage).toBeLessThanOrEqual(0.6);
      expect(ds.maxBarThickness).toBeLessThanOrEqual(48);
    }
  });
});

describe("Promise to Pay in the record", () => {
  it("shows status, promised amount, last day of the grace period, payments and the alerts that went out", async () => {
    signedIn();
    const d = detail({
      classification: "PTP", promise_status: "ESCALATED",
      ptp_commitments: [{ id: 1, status: "ESCALATED", instalment_no: 1, promise_date: "2026-11-10", broken_on: "2026-11-14", amount: "8300.000", currency: "SGD",
        amount_received: null, payments: [{ entry_id: "ENT-000500", date: "2026-11-09", applied: "100" }], alerted_at: "2026-11-14T09:00:00Z", escalated_at: "2026-11-16T09:00:00Z", check_note: null }],
    });
    renderApp(fakeDs({ workItem: async () => d }), "#/queue?record=ENT-000001");
    const section = await screen.findByText("🤝 Promise to Pay");
    const box = section.closest("[data-section]") as HTMLElement;
    expect(within(box).getByText("Escalated")).toBeInTheDocument();
    expect(box).toHaveTextContent("8,300.00 SGD");
    expect(box).toHaveTextContent("13 Nov 2026"); // broken_on - 1 day = promise 10 Nov + 3 days of grace
    expect(box).toHaveTextContent("Collections alerted");
    expect(box).toHaveTextContent("AR Supervisor alerted");
    expect(box).toHaveTextContent("ENT-000500");
  });

  it("is not there for a record without a promise", async () => {
    signedIn();
    renderApp(fakeDs({ workItem: async () => detail() }), "#/queue?record=ENT-000001");
    await screen.findByText("📧 Email Details");
    expect(screen.queryByText("🤝 Promise to Pay")).not.toBeInTheDocument();
  });
});

describe("Demo Control", () => {
  it("has the Reset demo button at the top, next to the title (not at the end of a long page)", async () => {
    signedIn();
    renderApp(fakeDs({ demoState: async () => ({ business_date: "2026-10-28", default_business_date: "2026-10-28", live_set_error: null, sent_total: 0, live_set: [],
      reset_point: { taken_at: "2026-11-03T10:00:00Z", taken_by: "x", business_date: "2026-10-28", counts: { "ar.work_item": 505 } } }) }), "#/demo");
    const reset = await screen.findByTestId("demo-reset");
    expect(reset).toBeEnabled();
    expect(reset.closest(".page-header")).not.toBeNull();
    expect(within(reset.closest(".page-header") as HTMLElement).getByRole("button", { name: /Process now/ })).toBeInTheDocument();
    fireEvent.click(reset);
    expect(await screen.findByRole("dialog", { name: "Reset demo" })).toBeInTheDocument();
  });
});
