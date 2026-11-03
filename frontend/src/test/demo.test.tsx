/* M11: Demo Control page. */
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DemoState } from "../data";
import { fakeDs, renderApp, signedIn } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => cleanup());

const sample = (code: string, over = {}) => ({ code, scenario: code.split("-")[0], from: "ap@customer.example", subject: `Remittance ${code}`, attachments: ["advice.pdf"], sent_count: 0, last_sent_at: null, last_sent_by: null, ...over });
const state = (over: Partial<DemoState> = {}): DemoState => ({
  business_date: "2026-10-28", default_business_date: "2026-10-28", live_set_error: null, sent_total: 0,
  reset_point: { taken_at: "2026-10-27T10:00:00Z", taken_by: "build_history", business_date: "2026-10-28", counts: { "ar.work_item": 250 } },
  live_set: [sample("R01-0001"), sample("P03-0193"), sample("P03R-0194", { sent_count: 2, last_sent_at: "2026-10-28T09:00:00Z", last_sent_by: "analyst@acme-demo.local" })], ...over,
});

describe("Demo Control", () => {
  it("shows the business date, the reset point and the live set with what was already sent", async () => {
    signedIn();
    renderApp(fakeDs({ demoState: async () => state() }), "#/demo");
    expect(await screen.findByText("R01-0001")).toBeInTheDocument();
    expect(screen.getByTestId("demo-date")).toHaveTextContent("28 Oct 2026");
    expect(screen.getByText(/250 work items/)).toBeInTheDocument();
    const row = screen.getByText("P03R-0194").closest("tr")!;
    expect(within(row).getByText(/2×/)).toBeInTheDocument();
    expect(within(row).getByText("Payment after a promise")).toBeInTheDocument();
  });

  it("sends a sample through the data layer and says whether the worker was started", async () => {
    signedIn();
    const demoSendSample = vi.fn(async (code: string, _p: boolean) => ({ code, gmail_id: "g1", from: "x", subject: "Payment commitment", worker: { started: true } }));
    renderApp(fakeDs({ demoState: async () => state(), demoSendSample }), "#/demo");
    fireEvent.click(await screen.findByLabelText("Send P03-0193"));
    await waitFor(() => expect(demoSendSample).toHaveBeenCalledWith("P03-0193", true));
    expect(await screen.findByText(/P03-0193 sent to the inbox/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Start processing right away/));
    fireEvent.click(screen.getByLabelText("Send R01-0001"));
    await waitFor(() => expect(demoSendSample).toHaveBeenCalledWith("R01-0001", false));
  });

  it("moves the business date by days or to a chosen date and reports the promise check", async () => {
    signedIn();
    const demoSetBusinessDate = vi.fn(async () => ({ business_date: "2026-11-27", before: "2026-10-28", ptp: { checked: 7, changed: ["a", "b"], alerts: 2, escalations: 1 }, worker: { started: true } }));
    renderApp(fakeDs({ demoState: async () => state(), demoSetBusinessDate }), "#/demo");
    fireEvent.click(await screen.findByRole("button", { name: "+30 days" }));
    await waitFor(() => expect(demoSetBusinessDate).toHaveBeenCalledWith({ add_days: 30 }));
    expect(await screen.findByText(/Business date is now 27 Nov 2026\. Promises checked: 2 changed, 2 alert\(s\) and 1 escalation\(s\) e-mailed/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Business date"), { target: { value: "2026-12-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Set date" }));
    await waitFor(() => expect(demoSetBusinessDate).toHaveBeenCalledWith({ date: "2026-12-01" }));
    fireEvent.click(screen.getByRole("button", { name: /Back to 28 Oct 2026/ }));
    await waitFor(() => expect(demoSetBusinessDate).toHaveBeenCalledWith({ date: "2026-10-28" }));
  });

  it("asks for confirmation before it resets, and does nothing when cancelled", async () => {
    signedIn();
    const demoReset = vi.fn(fakeDs().demoReset);
    renderApp(fakeDs({ demoState: async () => state(), demoReset }), "#/demo");
    fireEvent.click(await screen.findByTestId("demo-reset"));
    const dlg = await screen.findByRole("dialog", { name: "Reset demo" });
    expect(dlg).toHaveTextContent(/exported-cases list, promise statuses, sent samples and the business date/);
    fireEvent.click(within(dlg).getByRole("button", { name: "Cancel" }));
    expect(demoReset).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("demo-reset"));
    fireEvent.click(within(await screen.findByRole("dialog", { name: "Reset demo" })).getByRole("button", { name: "Reset demo" }));
    await waitFor(() => expect(demoReset).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/Demo reset to/)).toBeInTheDocument();
  });

  it("cannot reset without a reset point, and shows a refusal from the server", async () => {
    signedIn();
    renderApp(fakeDs({ demoState: async () => state({ reset_point: null }) }), "#/demo");
    expect(await screen.findByText(/no reset point yet/)).toBeInTheDocument();
    expect(screen.getByTestId("demo-reset")).toBeDisabled();
    cleanup();
    const demoProcessNow = vi.fn(async () => { throw new Error("Gmail is not configured."); });
    renderApp(fakeDs({ demoState: async () => state(), demoProcessNow }), "#/demo");
    fireEvent.click(await screen.findByRole("button", { name: /Process now/ }));
    expect((await screen.findAllByText(/Gmail is not configured/)).length).toBeGreaterThan(0);
  });

  it("filters the live set", async () => {
    signedIn();
    renderApp(fakeDs({ demoState: async () => state() }), "#/demo");
    await screen.findByText("R01-0001");
    fireEvent.change(screen.getByLabelText("Filter samples"), { target: { value: "p03r" } });
    expect(screen.queryByText("R01-0001")).not.toBeInTheDocument();
    expect(screen.getByText("P03R-0194")).toBeInTheDocument();
  });
});
