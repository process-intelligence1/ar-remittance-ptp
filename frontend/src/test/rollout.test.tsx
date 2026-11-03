/* During a roll-out the API can still be the old version (no chart data, no BSID block): the screens must not crash. */
import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Kpis } from "../data";
import { detail, fakeDs, KPIS, renderApp, signedIn } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => cleanup());

describe("old API during a roll-out", () => {
  it("Dashboard: KPI cards still show, each chart says 'Chart data unavailable' instead of crashing", async () => {
    signedIn();
    const { charts: _omit, ...oldKpis } = KPIS;
    renderApp(fakeDs({ kpis: async () => oldKpis as unknown as Kpis }), "#/");
    expect(await screen.findByTestId("kpi-total")).toHaveTextContent("3");
    expect((await screen.findAllByTestId("chart-unavailable")).length).toBe(3);
    expect(screen.getAllByText("Chart data unavailable").length).toBe(3);
  });

  it("Dashboard: the charts appear when the new API answers", async () => {
    signedIn();
    renderApp(fakeDs(), "#/");
    await screen.findByTestId("kpi-total");
    expect(screen.queryByTestId("chart-unavailable")).not.toBeInTheDocument();
  });

  it("Record detail: opens without the BSID block (older API) and without crashing", async () => {
    signedIn();
    const { bsid: _bsid, ...old } = detail();
    renderApp(fakeDs({ workItem: async () => old as never }), "#/queue?record=ENT-000001");
    expect(await screen.findByRole("dialog", { name: "Record Detail" })).toBeInTheDocument();
    expect(await screen.findByText(/SAP BSID Match/)).toBeInTheDocument();
    expect(screen.getByText(/BSID match: Yes/)).toBeInTheDocument(); // falls back to the row's own match flag
  });
});
