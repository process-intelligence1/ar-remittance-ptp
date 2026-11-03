/* M09: actions through the data layer, versions (409), bulk, clarification e-mail, details dialog, Exported cases + the .xlsx file. */
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import ExcelJS from "exceljs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActionError, type ExportedCase } from "../data";
import { LiveDataSource } from "../data/live";
import { STATUS_BADGE, STATUS_LABELS } from "../data/labels";
import { buildWorkbook, COLUMNS, summarise } from "../export/cases";
import { detail, fakeDs, renderApp, row, signedIn } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => cleanup());

const dialog = (name: string) => screen.findByRole("dialog", { name });

function exportedCase(over: Partial<ExportedCase> = {}): ExportedCase {
  return {
    entry_id: "ENT-000001", email_ref: "EML-000001", received_at: "2026-10-12T09:00:00Z", sender_email: "ap@x.example", kunnr: "100001",
    customer_name: "Innova Care", company_code: "1000", invoice_ref: "INV-1", belnr: "9002600125", gjahr: "2026", buzei: "001",
    invoice_amount: 100, invoice_currency: "USD", paid_amount: 99, paid_currency: "USD", difference: -1, payment_date: "2026-10-10",
    payment_reference: "PAY-1", match_level: "EXACT", confidence: 92, decision: "AUTO_PROCESS", confirmed_by: "analyst@acme-demo.local",
    confirmed_at: "2026-10-28T10:00:00Z", comment: "ok", exported_at: null, exported_by: null, ...over,
  };
}

describe("actions in the Action Queue", () => {
  it("Reject needs a comment, then calls the data layer with the row version", async () => {
    signedIn();
    const performAction = vi.fn(fakeDs().performAction);
    renderApp(fakeDs({ performAction, rows: [row({ version: 4, allowed_actions: ["REJECT"] })] }), "#/queue");
    await screen.findByText("ENT-000001");
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "REJECT" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to Selected" }));
    const dlg = await dialog("Reject Record");
    const go = within(dlg).getByRole("button", { name: "Reject Record" });
    expect(go).toBeDisabled();
    fireEvent.change(within(dlg).getByLabelText(/Comment/), { target: { value: "not ours" } });
    fireEvent.click(go);
    await waitFor(() => expect(performAction).toHaveBeenCalledWith(1, { action: "REJECT", version: 4, comment: "not ours" }));
  });

  it("several selected records are sent in one bulk call", async () => {
    signedIn();
    const performBulk = vi.fn(fakeDs().performBulk);
    const rows = [row({ id: 1, entry_id: "ENT-000001", version: 2 }), row({ id: 2, entry_id: "ENT-000002", version: 5 })];
    renderApp(fakeDs({ performBulk, rows }), "#/queue");
    await screen.findByText("ENT-000002");
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    fireEvent.click(screen.getByLabelText("Select ENT-000002"));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "CONFIRM_ADD_EXCEL" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to Selected" }));
    const dlg = await dialog("Confirm & Add to Excel (2 records)");
    fireEvent.click(within(dlg).getByRole("button", { name: "Confirm & Add to Excel" }));
    await waitFor(() => expect(performBulk).toHaveBeenCalledWith({ action: "CONFIRM_ADD_EXCEL", comment: undefined, items: [{ id: 1, version: 2 }, { id: 2, version: 5 }] }));
  });

  it("a bulk refusal names the records that are not valid and keeps the dialog open", async () => {
    signedIn();
    const performBulk = vi.fn(async () => { throw new ActionError("1 of 2 selected records cannot be processed - nothing was changed.", 422, [{ entry_id: "ENT-000002", message: "Cannot confirm: invoice number missing." }]); });
    const rows = [row({ id: 1, entry_id: "ENT-000001" }), row({ id: 2, entry_id: "ENT-000002" })];
    renderApp(fakeDs({ performBulk, rows }), "#/queue");
    await screen.findByText("ENT-000002");
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    fireEvent.click(screen.getByLabelText("Select ENT-000002"));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "CONFIRM_ADD_EXCEL" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to Selected" }));
    const dlg = await dialog("Confirm & Add to Excel (2 records)");
    fireEvent.click(within(dlg).getByRole("button", { name: "Confirm & Add to Excel" }));
    expect(await within(dlg).findByRole("alert")).toHaveTextContent("ENT-000002: Cannot confirm: invoice number missing.");
  });

  it("a stale version shows 'changed by someone else' and reloads the list", async () => {
    signedIn();
    const performAction = vi.fn(async () => { throw new ActionError("This record was changed by someone else - refresh and try again.", 409); });
    const workItems = vi.fn(fakeDs().workItems);
    renderApp(fakeDs({ performAction, workItems }), "#/queue");
    await screen.findByText("ENT-000001");
    const calls = workItems.mock.calls.length;
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "CONFIRM_ADD_EXCEL" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to Selected" }));
    fireEvent.click(within(await dialog("Confirm & Add to Excel")).getByRole("button", { name: "Confirm & Add to Excel" }));
    expect((await screen.findAllByText(/changed by someone else/)).length).toBeGreaterThan(0);
    await waitFor(() => expect(workItems.mock.calls.length).toBeGreaterThan(calls));
  });

  it("only actions that work on several records are offered in bulk", async () => {
    signedIn();
    renderApp(fakeDs({ rows: [row({ allowed_actions: ["CONFIRM_ADD_EXCEL", "REQUEST_CLARIFICATION", "ADD_UPDATE_DETAILS", "ESCALATE_TO_SUPERVISOR"] })] }), "#/queue");
    await screen.findByText("ENT-000001");
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    const names = within(screen.getByLabelText("Bulk action")).getAllByRole("option").map((o) => o.textContent);
    expect(names).toEqual(["Select bulk action", "Confirm & Add to Excel (1)", "Escalate to AR Supervisor"]);
  });

  it("the new statuses have a label and a badge, and can be filtered", async () => {
    expect(STATUS_LABELS.AWAITING_CUSTOMER).toBe("Awaiting Customer");
    expect(STATUS_LABELS.ESCALATED).toBe("Escalated");
    expect(STATUS_BADGE.AWAITING_CUSTOMER).toBeTruthy();
    expect(STATUS_BADGE.ESCALATED).toBeTruthy();
    signedIn();
    renderApp(fakeDs(), "#/queue");
    await screen.findByText("ENT-000001");
    const options = within(screen.getByLabelText("Status")).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(expect.arrayContaining(["Awaiting Customer", "Escalated", "Confirmed", "Rejected"]));
  });
});

describe("out-of-scope e-mails are not in the Action Queue", () => {
  it("asks the data layer for in-scope rows only, and offers no Out of Scope classification or status filter", async () => {
    signedIn();
    const workItems = vi.fn(fakeDs().workItems);
    renderApp(fakeDs({ workItems }), "#/queue");
    await screen.findByText("ENT-000001");
    expect(workItems.mock.calls.some(([p]) => p.page_size === 25 && p.in_scope === true)).toBe(true);
    expect(workItems.mock.calls.filter(([p]) => p.in_scope !== true && p.status !== "CONFIRMED")).toEqual([]);
    expect(within(screen.getByLabelText("Classification")).queryByRole("option", { name: "Out of Scope" })).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("Status")).queryByRole("option", { name: /Ignored/ })).not.toBeInTheDocument();
  });
});

describe("clarification e-mail and details dialogs", () => {
  it("Request Clarification previews the e-mail, lets the analyst edit it and sends it through the data layer", async () => {
    signedIn();
    const performAction = vi.fn(async (_id: number | string, r: { version: number }) => ({ item: row({ version: r.version + 1 }), outbound_id: 9, worker_started: true }));
    const ds = fakeDs({ performAction, workItem: async () => detail({ allowed_actions: ["REQUEST_CLARIFICATION"] }) });
    renderApp(ds, "#/queue?record=ENT-000001");
    fireEvent.click(await screen.findByRole("button", { name: "Request Clarification" }));
    const dlg = await dialog("Request Clarification · ENT-000001");
    expect(await within(dlg).findByText(/delivered to/, { exact: false })).toHaveTextContent("demo@mailbox.example");
    const text = within(dlg).getByLabelText("Text") as HTMLTextAreaElement;
    await waitFor(() => expect(text.value).toContain("please confirm"));
    fireEvent.change(text, { target: { value: text.value + "\nThanks!" } });
    fireEvent.click(within(dlg).getByRole("button", { name: "Send e-mail" }));
    await waitFor(() => expect(performAction).toHaveBeenCalled());
    const [id, req] = performAction.mock.calls[0] as unknown as [number, { action: string; version: number; email: { subject: string; body: string } }];
    expect(id).toBe(1);
    expect(req.action).toBe("REQUEST_CLARIFICATION");
    expect(req.email.subject).toContain("[AR-DEMO][CLARIFICATION → ap@x.example]");
    expect(req.email.body.endsWith("Thanks!")).toBe(true);
  });

  it("Add / Update details sends only the changed fields and the BSID item picked in the dialog", async () => {
    signedIn();
    const performAction = vi.fn(fakeDs().performAction);
    const ds = fakeDs({ performAction, workItem: async () => detail({ allowed_actions: ["ADD_UPDATE_DETAILS"] }) });
    renderApp(ds, "#/queue?record=ENT-000001");
    fireEvent.click(await screen.findByRole("button", { name: "Add / Update Invoice Details" }));
    const dlg = await dialog("Add / Update Invoice Details · ENT-000001");
    const save = within(dlg).getByRole("button", { name: "Save and score again" });
    await waitFor(() => expect((within(dlg).getByLabelText("Invoice number") as HTMLInputElement).value).toBe("INV-1"));
    expect(save).toBeDisabled(); // nothing changed yet
    fireEvent.change(within(dlg).getByLabelText("Invoice number"), { target: { value: "INV-2" } });
    fireEvent.change(within(dlg).getByLabelText("Amount"), { target: { value: "250.5" } });
    fireEvent.click(await within(dlg).findByLabelText("Select BSID 9002600125"));
    fireEvent.click(save);
    await waitFor(() => expect(performAction).toHaveBeenCalled());
    expect(performAction.mock.calls[0]).toEqual([1, { action: "ADD_UPDATE_DETAILS", version: 1, details: { invoice_ref: "INV-2", amount: "250.5", bsid_id: 7 } }]);
  });

  it("the Record Detail of a confirmed record offers no actions", async () => {
    signedIn();
    renderApp(fakeDs({ workItem: async () => detail({ status: "CONFIRMED", allowed_actions: [], confirmed_by: "analyst@acme-demo.local", confirmed_at: "2026-10-28T10:00:00Z" }) }), "#/queue?record=ENT-000001");
    expect(await screen.findByText(/No actions available for your role/)).toBeInTheDocument();
    expect(screen.getByText(/Confirmed by analyst@acme-demo.local/)).toBeInTheDocument();
  });
});

describe("Exported cases", () => {
  it("shows all confirmed cases in an Excel-style view with a Summary sheet, and downloading records the export", async () => {
    signedIn();
    const markExported = vi.fn(async () => 2);
    const items = [exportedCase(), exportedCase({ entry_id: "ENT-000002", paid_amount: 50, invoice_amount: 50, difference: 0 })];
    const createObjectURL = vi.fn(() => "blob:x");
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
    renderApp(fakeDs({ exportedCases: async () => ({ count: 2, items }), markExported }), "#/queue");
    fireEvent.click(await screen.findByTestId("exported-cases-button"));
    const dlg = await dialog("Exported cases");
    expect(await within(dlg).findByText("ENT-000002")).toBeInTheDocument();
    expect(within(dlg).getAllByRole("columnheader", { name: /^[A-Z]$/ }).length).toBeGreaterThan(20); // column letters A, B, C ...
    expect(within(dlg).getByRole("columnheader", { name: "Invoice No." })).toBeInTheDocument();
    expect(within(dlg).getByRole("tab", { name: "Cases" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(within(dlg).getByRole("tab", { name: "Summary" }));
    expect(within(dlg).getByRole("columnheader", { name: "Cases" })).toBeInTheDocument();
    expect(within(dlg).getByText("Innova Care")).toBeInTheDocument();
    fireEvent.click(within(dlg).getByRole("button", { name: /Download \.xlsx/ }));
    await waitFor(() => expect(markExported).toHaveBeenCalledWith(["ENT-000001", "ENT-000002"]));
    expect(createObjectURL).toHaveBeenCalled();
  });
});

describe("the .xlsx file", () => {
  it("has the sheets Cases and Summary with every confirmed case and the agreed columns", async () => {
    const items = [exportedCase(), exportedCase({ entry_id: "ENT-000002", paid_amount: 50, invoice_amount: 50, difference: 0 }),
      exportedCase({ entry_id: "ENT-000003", kunnr: "100002", customer_name: "Zeta GmbH", invoice_currency: "EUR", paid_currency: "EUR", belnr: null })];
    const buffer = await buildWorkbook(items);
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.load(buffer);
    expect(wb.worksheets.map((w) => w.name)).toEqual(["Cases", "Summary"]);
    const cases = wb.getWorksheet("Cases")!;
    expect(cases.rowCount).toBe(1 + items.length);
    expect(cases.getRow(1).values).toEqual([undefined, ...COLUMNS.map((c) => c.header)]);
    const headers = COLUMNS.map((c) => c.header);
    const cell = (r: number, h: string) => cases.getRow(r).getCell(headers.indexOf(h) + 1).value;
    expect(cell(2, "Entry ID")).toBe("ENT-000001");
    expect(cell(2, "BSID Document (BELNR / GJAHR / BUZEI)")).toBe("9002600125 / 2026 / 001");
    expect(cell(2, "Invoice Amount")).toBe(100);
    expect(cell(2, "Difference")).toBe(-1);
    expect(cell(2, "Payment Date")).toBeInstanceOf(Date);
    expect(cell(4, "BSID Document (BELNR / GJAHR / BUZEI)")).toBeNull();
    const sum = wb.getWorksheet("Summary")!;
    expect(sum.rowCount).toBe(1 + 2); // Innova Care USD, Zeta EUR - currencies are not added together
    expect(sum.getRow(2).values).toEqual([undefined, "100001", "Innova Care", "USD", 2, 150, 149, -1]);
  });

  it("adds up per customer and currency", () => {
    const s = summarise([exportedCase(), exportedCase({ entry_id: "B", paid_currency: "EUR" })]);
    expect(s.map((x) => [x.currency, x.cases])).toEqual([["EUR", 1], ["USD", 1]]);
  });
});

describe("live data source: actions", () => {
  it("posts the action with its version and turns a refusal into an ActionError", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/actions") && (JSON.parse(String(init?.body)).version === 1)) return new Response(JSON.stringify({ detail: { message: "This record was changed by someone else - refresh and try again.", problems: [] } }), { status: 409 });
      return new Response(JSON.stringify({ item: {}, outbound_id: null, worker_started: null }), { status: 200 });
    }));
    const ds = new LiveDataSource("https://api.example");
    ds.setToken("t");
    await ds.performAction("ENT-000009", { action: "REJECT", version: 2, comment: "x" });
    expect(calls[0].url).toBe("https://api.example/api/work-items/ENT-000009/actions");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ action: "REJECT", version: 2, comment: "x" });
    await expect(ds.performAction(9, { action: "REJECT", version: 1 })).rejects.toMatchObject({ status: 409, message: expect.stringContaining("changed by someone else") });
    vi.unstubAllGlobals();
  });
});
