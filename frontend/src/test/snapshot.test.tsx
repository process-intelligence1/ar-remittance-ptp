/* M15: the demo edition's data source, rules, KPIs and screens. */
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActionError, type PtpList } from "../data";
import { allowedActions } from "../data/permissions";
import { SnapshotDataSource } from "../data/snapshot";
import { computeKpis } from "../data/snapshot/kpis";
import { applyFilters, sortRows, type SnapRow } from "../data/snapshot/rows";
import { DEFAULT_QUESTION, fill, rawTemplates, renderClarification } from "../data/snapshot/templates";
import { renderApp } from "./helpers";

import fixture from "../../../data/eval/snapshot_rules_fixture.json";

// The exported demo data (snapshot/data) is only there after scripts.export_snapshot ran; the KPI check below uses it when it exists.
const exported = import.meta.glob("../../../snapshot/data/{work_items,kpis_expected}.json", { eager: true, import: "default" }) as Record<string, unknown>;
const exportedRows = exported["../../../snapshot/data/work_items.json"] as SnapRow[] | undefined;
const exportedOracle = exported["../../../snapshot/data/kpis_expected.json"] as { filters: Record<string, string | number>; kpis: unknown }[] | undefined;

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------- parity with the Python code (shared fixture)
describe("the browser's rules equal the server's", () => {
  it("allowed actions: all 2,800 combinations of role, decision, status, assignee and 'resolved' agree with app/permissions.py", () => {
    expect(fixture.cases.length).toBe(2800);
    const wrong = (fixture.cases as { role: string; decision: string | null; status: string; assigned_role: string | null; resolved: boolean; allowed: string[] }[]).filter((c) =>
      JSON.stringify(allowedActions(c.role, c.decision, c.status, c.assigned_role, c.resolved)) !== JSON.stringify(c.allowed));
    expect(wrong).toEqual([]);
  });

  it("the clarification e-mail text in every language equals app/outbound.py's template", () => {
    const { ctx, default_question: dq, rendered } = fixture.templates as { ctx: Record<string, string>; default_question: Record<string, string>; rendered: Record<string, { subject: string; body: string }> };
    expect(DEFAULT_QUESTION).toEqual(dq);
    for (const lang of Object.keys(rendered)) {
      const c = { ...ctx, question: dq[lang] };
      expect(fill(rawTemplates[lang].subject, c)).toBe(rendered[lang].subject);
      expect(fill(rawTemplates[lang].body, c)).toBe(rendered[lang].body);
    }
  });

  it.runIf(!!exportedRows && !!exportedOracle)("KPIs, distributions, trend and chart data computed in the browser equal what the API answered for the same rows", () => {
    const rows = exportedRows!, oracle = exportedOracle!;
    expect(oracle.length).toBeGreaterThan(5);
    for (const o of oracle) {
      const mine = JSON.parse(JSON.stringify(computeKpis(rows, o.filters as never)));
      expect(mine, JSON.stringify(o.filters)).toEqual(o.kpis);
    }
  });
});

// ---------------------------------------------------------------- a small in-memory snapshot
function row(over: Partial<SnapRow> = {}, exp: Partial<SnapRow["export"]> = {}): SnapRow {
  const n = over.id ?? 1;
  return {
    id: n, entry_id: `ENT-${String(n).padStart(6, "0")}`, email_ref: `EML-${String(n).padStart(6, "0")}`, received_at: "2026-10-12T09:00:00+00:00", sender_email: "ap@x.example",
    subject: "Remittance", customer_name: "Innova Care", kunnr: "0000100001", company_code: "1000", region: "EMEA", classification: "REMITTANCE", line_type: "REMITTANCE",
    invoice_ref: `INV-${n}`, match_field: "XBLNR", match_level: "EXACT", bsid_match: true, amount: 100, currency: "USD", amount_usd: 100, usd_status: "OK", confidence: 92,
    confidence_source: "FAST_PATH", decision: "AUTO_PROCESS", status: "AUTO_PROCESSED", exception_reason: null, review_reasons: null, recommended_action: "Confirm & Add to Excel",
    assigned_role: "CASH_APPLICATION", sla_due_at: null, duplicate_of: null, updated_at: "2026-10-12T09:00:00+00:00", version: 1, resolved: false, ...over,
    export: { payment_date: "2026-10-10", payment_reference: "PAY-1", belnr: "9002600125", gjahr: "2026", buzei: "001", bsid_amount: 100, bsid_currency: "USD", language: "de",
      source: "history", email_business_date: "2026-10-12", invoice_ref_norm: `INV${n}`, ...exp },
  } as SnapRow;
}

const ROWS = [
  row({ id: 1 }),
  row({ id: 2, status: "PENDING_REVIEW", decision: "MANUAL_REVIEW", confidence: 77.2, match_level: "NEAR", customer_name: "Rheinwerk GmbH", kunnr: "0000100645", company_code: "2000", amount: 50, amount_usd: 55 }),
  row({ id: 3, status: "EXCEPTION", decision: "EXCEPTION", classification: "EXCEPTION", bsid_match: false, confidence: 12, amount: null, amount_usd: null, usd_status: "NO_AMOUNT", assigned_role: "AR_ANALYST" }),
  row({ id: 4, status: "DUPLICATE", decision: "DUPLICATE", classification: "DUPLICATE", assigned_role: "AR_ANALYST", duplicate_of: "ENT-000001" }),
  row({ id: 5, status: "IGNORED", decision: "OUT_OF_SCOPE", classification: "OUT_OF_SCOPE", invoice_ref: null, customer_name: null, kunnr: null, amount: null, amount_usd: null, usd_status: "NO_AMOUNT", confidence: 0, assigned_role: null }),
  row({ id: 6, status: "PENDING_REVIEW", decision: "MANUAL_INVESTIGATION", assigned_role: "AR_ANALYST", confidence: 30, received_at: "2026-10-20T09:00:00+00:00" }),
];

function stubFetch(rows: SnapRow[] = ROWS) {
  const files: Record<string, unknown> = {
    "data/work_items.json": rows, "data/audit.json": [{ id: 1, occurred_at: "2026-10-12T10:00:00+00:00", business_date: "2026-10-12", actor: "system", actor_role: null, entity_type: "work_item", entity_id: "ENT-000001", action: "WORK_ITEMS_CREATED", details: null }],
    "data/ptp.json": { business_date: "2026-10-28", grace_days: 3, total: 0, page: 1, page_size: 100, counts: { OPEN: 0, PARTIALLY_KEPT: 0, KEPT: 0, BROKEN: 0, ESCALATED: 0, CANCELLED: 0 }, items: [] },
    "data/meta.json": { business_date: "2026-10-28", generated_at: "2026-11-03T10:00:00Z" },
  };
  for (const r of rows) {
    const { export: _e, ...base } = r;
    files[`data/details/${r.entry_id}.json`] = { ...base, work_item: { status: r.status, payment_date: "2026-10-10" }, email: { body_text: "hi" }, attachments: [
      { id: 7, parent_id: null, filename: "advice.pdf", mime_type: "application/pdf", page_count: 2, viewable_inline: true, file: "emails/R01-0001/advice.pdf", file_kind: "sample", pages_url: "pages/7/{page}.jpg" }],
      candidates: [], score_breakdown: {}, ptp_commitments: [], same_email_items: [], audit: [{ id: 1, entity_id: r.entry_id, action: "WORK_ITEMS_CREATED" }] };
  }
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = String(url).replace(/^.*?(data\/.*)$/, "$1");
    return key in files ? new Response(JSON.stringify(files[key]), { status: 200 }) : new Response("{}", { status: 404 });
  }));
}

async function ds(role = "analyst@acme-demo.local") {
  stubFetch();
  const d = new SnapshotDataSource("/ar/");
  await d.login(role);
  return d;
}

describe("demo edition data source", () => {
  it("lists, filters, sorts and pages like the API, and says which actions the signed-in role may take", async () => {
    const d = await ds();
    const all = await d.workItems({ page_size: 50 });
    expect(all.total).toBe(6);
    expect(all.items[0].entry_id).toBe("ENT-000006"); // newest received first (id breaks ties, newest id first)
    expect(all.items.map((r) => r.entry_id)).toEqual(["ENT-000006", "ENT-000005", "ENT-000004", "ENT-000003", "ENT-000002", "ENT-000001"]);
    expect((await d.workItems({ status: "pending_review" })).total).toBe(2);
    expect((await d.workItems({ customer: "rheinwerk" })).items.map((r) => r.entry_id)).toEqual(["ENT-000002"]);
    expect((await d.workItems({ customer: "100645" })).total).toBe(1);
    expect((await d.workItems({ min_confidence: 80 })).items.map((r) => r.id)).toEqual([4, 1]); // only the two rows at 92 %
    expect((await d.workItems({ bsid_match: "false" })).total).toBe(1);
    expect((await d.workItems({ from_date: "2026-10-15" })).total).toBe(1);
    expect((await d.workItems({ q: "inv-3" })).total).toBe(1);
    expect((await d.workItems({ sort: "amount", order: "asc" })).items.map((r) => r.amount).slice(-2)).toEqual([null, null]); // empty values last
    const page2 = await d.workItems({ page: 2, page_size: 4 });
    expect(page2.items.length).toBe(2);
    const cash = new SnapshotDataSource("/ar/");
    await cash.login("cashapp@acme-demo.local");
    expect((await cash.workItems({})).items.find((r) => r.id === 3)!.allowed_actions).toEqual([]); // an exception is the analyst's, not Cash Application's
    expect((await d.workItems({})).items.find((r) => r.id === 3)!.allowed_actions).toContain("REQUEST_CLARIFICATION");
  });

  it("confirm: status CONFIRMED, version up, audit entry with before / after, then no further action; the Dashboard follows at once", async () => {
    const d = await ds();
    const kBefore = await d.kpis({});
    const out = await d.performAction(1, { action: "CONFIRM_ADD_EXCEL", version: 1, comment: "ok" });
    expect(out.item.status).toBe("CONFIRMED");
    expect(out.item.version).toBe(2);
    expect(out.item.allowed_actions).toEqual([]);
    const detail = await d.workItem("ENT-000001");
    const entry = detail.audit.at(-1)!;
    expect(entry.action).toBe("CONFIRM_ADD_EXCEL");
    expect(entry.actor).toBe("analyst@acme-demo.local");
    expect((entry.details as { before: { status: string }; after: { status: string }; comment: string })).toMatchObject({ before: { status: "AUTO_PROCESSED" }, after: { status: "CONFIRMED" }, comment: "ok" });
    expect(detail.allowed_actions).toEqual([]);
    expect((await d.audit({ entity_id: "ENT-000001" })).items[0].action).toBe("CONFIRM_ADD_EXCEL");
    // status changes never move a row between Auto / Manual / Exception / Duplicate (decision-based) ...
    const kAfter = await d.kpis({});
    expect(kAfter.cards).toEqual(kBefore.cards);
    // ... but the status distribution and the exported-cases count follow immediately
    expect(kAfter.distributions.status.find((s) => s.label === "CONFIRMED")!.count).toBe(1);
    expect((await d.workItems({ status: "CONFIRMED", page_size: 1 })).total).toBe(1);
  });

  it("refuses a stale version (409), a missing comment, an action the role may not take, and the actions that need the live system", async () => {
    const d = await ds();
    await expect(d.performAction(1, { action: "CONFIRM_ADD_EXCEL", version: 9 })).rejects.toMatchObject({ status: 409 });
    await expect(d.performAction(2, { action: "REJECT", version: 1 })).rejects.toMatchObject({ status: 422 });
    await expect(d.performAction(1, { action: "REJECT", version: 1, comment: "x" })).rejects.toMatchObject({ status: 403 });
    await expect(d.performAction(2, { action: "ADD_UPDATE_DETAILS", version: 1, details: { amount: "5" } })).rejects.toMatchObject({ status: 422, message: expect.stringContaining("live system") });
    await expect(d.performAction(4, { action: "MARK_NON_DUPLICATE", version: 1 })).rejects.toMatchObject({ status: 422 });
  });

  it("an incomplete row cannot be confirmed (invoice number, customer, BSID match or amount)", async () => {
    stubFetch([row({ id: 1, status: "PENDING_REVIEW", decision: "MANUAL_REVIEW", bsid_match: false, amount: null, assigned_role: "AR_ANALYST" })]);
    const d = new SnapshotDataSource("/ar/");
    await d.login("analyst@acme-demo.local");
    await expect(d.performAction(1, { action: "CONFIRM_ADD_EXCEL", version: 1 })).rejects.toMatchObject({ status: 422, message: expect.stringContaining("BSID match or an amount") });
  });

  it("reject, escalate (to the supervisor only), clarify (a preview: nothing is sent) and close as duplicate set the right status", async () => {
    const d = await ds();
    expect((await d.performAction(2, { action: "REJECT", version: 1, comment: "not ours" })).item.status).toBe("REJECTED");
    const esc = await d.performAction(6, { action: "ESCALATE_TO_SUPERVISOR", version: 1, comment: "big" });
    expect(esc.item).toMatchObject({ status: "ESCALATED", assigned_role: "AR_SUPERVISOR", allowed_actions: [] });
    const sup = new SnapshotDataSource("/ar/");
    await sup.login("supervisor@acme-demo.local");
    expect((await sup.workItems({})).items.find((r) => r.id === 6)!.allowed_actions).not.toContain("ESCALATE_TO_SUPERVISOR");
    const draft = await d.previewEmail(3, "Which invoice?");
    expect(draft.subject).toMatch(/^\[AR-DEMO\]\[CLARIFICATION → ap@x\.example\]/);
    expect(draft.body).toContain("Which invoice?");
    expect(draft.actual_recipient).toMatch(/preview only/);
    await expect(d.performAction(3, { action: "REQUEST_CLARIFICATION", version: 1, email: { subject: "", body: "" } })).rejects.toMatchObject({ status: 422 });
    const clar = await d.performAction(3, { action: "REQUEST_CLARIFICATION", version: 1, email: { subject: draft.subject, body: draft.body } });
    expect(clar.item.status).toBe("AWAITING_CUSTOMER");
    expect(clar.worker_started).toBeNull();
    expect((await d.performAction(4, { action: "CLOSE_AS_DUPLICATE", version: 1 })).item.status).toBe("RESOLVED");
  });

  it("bulk is all or nothing and names the rows that are not valid", async () => {
    const d = await ds();
    const bad = await d.performBulk({ action: "CONFIRM_ADD_EXCEL", items: [{ id: 1, version: 1 }, { id: 2, version: 1 }, { id: 3, version: 1 }] }).catch((e) => e);
    expect(bad).toBeInstanceOf(ActionError);
    expect((bad as ActionError).problems.map((p) => p.entry_id)).toEqual(["ENT-000003"]); // the exception has no amount but a customer: it is the invoice-less one that fails
    expect((await d.workItem(1)).status).toBe("AUTO_PROCESSED"); // nothing changed
    const ok = await d.performBulk({ action: "CONFIRM_ADD_EXCEL", items: [{ id: 1, version: 1 }, { id: 2, version: 1 }] });
    expect(ok.done).toBe(2);
    expect((await d.workItems({ status: "CONFIRMED" })).total).toBe(2);
    await expect(d.performBulk({ action: "ADD_UPDATE_DETAILS", items: [{ id: 1, version: 3 }] })).rejects.toMatchObject({ status: 422 });
  });

  it("Exported cases lists all confirmed rows with the Excel columns, and a download is recorded", async () => {
    const d = await ds();
    await d.performBulk({ action: "CONFIRM_ADD_EXCEL", items: [{ id: 1, version: 1 }, { id: 2, version: 1 }], comment: "posted" });
    const ex = await d.exportedCases();
    expect(ex.count).toBe(2);
    expect(ex.items[0]).toMatchObject({ entry_id: "ENT-000001", kunnr: "100001", belnr: "9002600125", invoice_amount: 100, paid_amount: 100, difference: 0, comment: "posted", confirmed_by: "analyst@acme-demo.local", exported_at: null });
    expect(ex.items[1].difference).toBe(-50);
    expect(await d.markExported(["ENT-000001"])).toBe(1);
    expect((await d.exportedCases()).items[0]).toMatchObject({ exported_by: "analyst@acme-demo.local" });
    expect((await d.exportedCases()).items[0].exported_at).toBeTruthy();
  });

  it("Reset puts back what was loaded; the record detail shows file and page links that work from the site root", async () => {
    const d = await ds();
    await d.performAction(1, { action: "CONFIRM_ADD_EXCEL", version: 1 });
    d.resetSnapshot();
    expect((await d.workItem(1)).status).toBe("AUTO_PROCESSED");
    expect((await d.workItem(1)).audit.map((a) => a.action)).toEqual(["WORK_ITEMS_CREATED"]);
    expect((await d.workItems({ status: "CONFIRMED" })).total).toBe(0);
    const att = (await d.workItem(1)).attachments[0];
    expect(d.resolveUrl(att.url)).toBe("/ar/samples/emails/R01-0001/advice.pdf");
    expect(d.resolveUrl(att.page_url!.replace("{page}", "2"))).toBe("/ar/pages/7/2.jpg");
    expect(d.resolveUrl("https://elsewhere.example/x")).toBe("https://elsewhere.example/x");
  });

  it("has no server-only features: Demo Control, the promise check and BSID picking say so", async () => {
    const d = await ds();
    await expect(d.demoState()).rejects.toThrow(/live edition/);
    await expect(d.runPtpChecks()).rejects.toThrow(/live edition/);
    await expect(d.bsidChoices(1)).rejects.toThrow(/live edition/);
    const p: PtpList = await d.ptpList({});
    expect(p.counts.OPEN).toBe(0);
  });
});

describe("row helpers", () => {
  it("filters and sorts like the API", () => {
    expect(applyFilters(ROWS, { classification: "remittance" }).length).toBe(3);
    expect(sortRows(ROWS, "confidence", "asc")[0].confidence).toBe(0);
    expect(sortRows(ROWS, "customer", "asc").at(-1)!.customer_name).toBeNull();
  });
  it("renders the template in the customer's language", () => {
    const mail = renderClarification(ROWS[0]);
    expect(mail.language).toBe("de");
    expect(mail.body).toContain("Sehr geehrte Damen und Herren (Innova Care)");
  });
});

// ---------------------------------------------------------------- the screens in demo mode
describe("demo edition screens", () => {
  it("login needs no access code, the banner and Reset are shown, Demo Control is hidden, re-scoring actions are disabled", async () => {
    stubFetch();
    const dataSource = new SnapshotDataSource("/");
    renderApp(dataSource, "#/queue?record=ENT-000002");
    const signIn = await screen.findByRole("button", { name: "Sign in" });
    await waitFor(() => expect(signIn).toBeEnabled()); // enabled once the (instant) health check and the user list are in
    fireEvent.click(signIn);
    expect(screen.queryByLabelText("Access code")).not.toBeInTheDocument();
    expect(await screen.findByTestId("snapshot-banner")).toHaveTextContent("changes reset on reload");
    expect(screen.queryByRole("link", { name: /Demo Control/ })).not.toBeInTheDocument();
    const update = await screen.findByRole("button", { name: "Add / Update Invoice Details" });
    expect(update).toBeDisabled();
    expect(update).toHaveAttribute("title", expect.stringContaining("live system"));
    // an action works and the queue shows it; Reset brings it back
    fireEvent.click(await screen.findByRole("button", { name: "Request Clarification" }));
    const dlg = await screen.findByRole("dialog", { name: /Request Clarification/ });
    expect(await within(dlg).findByText(/Nothing is sent here/)).toBeInTheDocument();
    fireEvent.click(await within(dlg).findByRole("button", { name: /Record \(nothing is sent\)/ }));
    await waitFor(async () => expect((await dataSource.workItem(2)).status).toBe("AWAITING_CUSTOMER"));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    await waitFor(async () => expect((await dataSource.workItem(2)).status).toBe("PENDING_REVIEW"));
  });
});
