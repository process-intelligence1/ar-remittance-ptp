/* M10: PTP Tracker screen. */
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PtpItem, PtpList } from "../data";
import { PTP_STATUS_LABELS } from "../data/labels";
import { fakeDs, renderApp, signedIn } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => cleanup());

function item(over: Partial<PtpItem> = {}): PtpItem {
  return {
    id: 1, work_item_id: 1, entry_id: "ENT-000389", email_ref: "EML-000100", sender_email: "ap@x.example", customer_name: "Pacific Rim Traders",
    kunnr: "0000102419", company_code: "5000", invoice_ref: "JP-26-002271", instalment_no: 1, promise_date: "2026-11-10", deadline: "2026-11-13",
    amount: 8300, currency: "SGD", status: "BROKEN", amount_received: null, days_overdue: 4, payments: [], alerted_at: "2026-11-14T09:00:00Z",
    escalated_at: null, check_note: null, last_checked_on: "2026-11-14", ...over,
  };
}

function list(items: PtpItem[]): PtpList {
  return {
    business_date: "2026-11-14", grace_days: 3, total: items.length, page: 1, page_size: 100,
    counts: { OPEN: 0, PARTIALLY_KEPT: 1, KEPT: 2, BROKEN: 1, ESCALATED: 1, CANCELLED: 0 }, items,
  };
}

describe("PTP Tracker", () => {
  it("is in the menu and shows the cards, the promises, their deadline and the alerts sent", async () => {
    signedIn();
    const rows = [item(), item({ id: 2, entry_id: "ENT-000390", status: "ESCALATED", escalated_at: "2026-11-16T09:00:00Z", days_overdue: 6 }),
      item({ id: 3, entry_id: "ENT-000391", status: "KEPT", days_overdue: 0, alerted_at: null, amount_received: 8300,
        payments: [{ entry_id: "ENT-000500", amount: "8300", currency: "SGD", date: "2026-11-12", applied: "8300" }] })];
    renderApp(fakeDs({ ptpList: async () => list(rows) }), "#/ptp");
    expect(await screen.findByText("ENT-000390")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /PTP Tracker/ })).toBeInTheDocument();
    expect(screen.getByTestId("ptp-card-BROKEN")).toHaveTextContent("Broken: 1");
    expect(screen.getByTestId("ptp-card-KEPT")).toHaveTextContent("Kept: 2");
    expect(screen.getAllByText(PTP_STATUS_LABELS.ESCALATED).length).toBeGreaterThan(0);
    const row = screen.getByText("ENT-000389").closest("tr")!;
    expect(within(row).getByText("8,300.00 SGD")).toBeInTheDocument();
    expect(within(row).getByTestId("alert-sent")).toBeInTheDocument();
    expect(within(screen.getByText("ENT-000390").closest("tr")!).getByTestId("escalation-sent")).toBeInTheDocument();
    expect(within(screen.getByText("ENT-000391").closest("tr")!).getByText(/ENT-000500/)).toBeInTheDocument();
  });

  it("filters by status through the data layer", async () => {
    signedIn();
    const ptpList = vi.fn(async (p: { status?: string }) => list(p.status === "BROKEN" ? [item()] : [item(), item({ id: 2, entry_id: "ENT-000390", status: "OPEN" })]));
    renderApp(fakeDs({ ptpList }), "#/ptp");
    await screen.findByText("ENT-000390");
    fireEvent.click(screen.getByTestId("ptp-card-BROKEN"));
    await waitFor(() => expect(ptpList).toHaveBeenCalledWith(expect.objectContaining({ status: "BROKEN" })));
    await waitFor(() => expect(screen.queryByText("ENT-000390")).not.toBeInTheDocument());
  });

  it("'Re-check now' runs the check and tells how many alerts went out", async () => {
    signedIn();
    const runPtpChecks = vi.fn(async () => ({ business_date: "2026-11-16", checked: 5, changed: ["ENT-000389/1: BROKEN -> ESCALATED"], alerts: 0, escalations: 1, counts: {} }));
    renderApp(fakeDs({ ptpList: async () => list([item()]), runPtpChecks }), "#/ptp");
    await screen.findByText("ENT-000389");
    fireEvent.click(screen.getByTestId("ptp-recheck"));
    expect(await screen.findByText(/Checked 5 promise\(s\) at 2026-11-16: 1 changed, 0 alert\(s\), 1 escalation\(s\) e-mailed/)).toBeInTheDocument();
    expect(runPtpChecks).toHaveBeenCalledTimes(1);
  });

  it("opens the record when a row is clicked", async () => {
    signedIn();
    renderApp(fakeDs({ ptpList: async () => list([item()]) }), "#/ptp");
    fireEvent.click((await screen.findByText("ENT-000389")).closest("tr")!);
    await waitFor(() => expect(window.location.hash).toBe("#/queue?record=ENT-000389"));
  });
});
