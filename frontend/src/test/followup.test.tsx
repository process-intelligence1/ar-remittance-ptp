/* M08 follow-up: Dashboard charts, record detail pop-up, labels, Exported cases button. */
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ACTION_LABELS } from "../data/labels";
import { aiExplanation, confidenceBadge, confidenceRows, fastPathBanner } from "../data/explain";
import sections from "../kb/sections.json";
import { performanceLabels, stackLabels } from "../pages/Dashboard";
import { detail, fakeDs, renderApp, row, signedIn } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Props = Record<string, any>;
const chartProps = () => (globalThis as unknown as { __chartProps: Props[] }).__chartProps;
const lastOf = (kind: string, pick: (p: Props) => boolean) => [...chartProps()].reverse().find((p) => p.kind === kind && pick(p))!;

describe("Dashboard charts (prototype types, titles, labels, colours)", () => {
  it("uses 'Auto Processed' on the cards and nowhere says 'AI Processed' in the page text", async () => {
    signedIn();
    const view = renderApp(fakeDs(), "#/");
    expect((await screen.findAllByText("Auto Processed", { exact: false })).length).toBeGreaterThan(0);
    expect(view.container.textContent).not.toMatch(/AI Processed/);
  });

  it("Performance Stability: horizontal stacked bars, Remittance / Promise-to-Pay, axis titles, green / orange / red", async () => {
    signedIn();
    renderApp(fakeDs(), "#/");
    await screen.findByTestId("kpi-total");
    const c = lastOf("bar", (p) => p.options?.indexAxis === "y");
    expect(c.data.labels).toEqual(["Remittance", "Promise-to-Pay"]);
    expect(c.data.datasets.map((d: Props) => [d.label, d.backgroundColor])).toEqual([["Auto Processed", "#059669"], ["Manual Processing", "#d97706"], ["Exceptions", "#dc2626"]]);
    expect(c.options.scales.x.title.text).toBe("Number of Emails");
    expect(c.options.scales.y.title.text).toBe("Classification");
    expect(c.options.scales.x.stacked && c.options.scales.y.stacked).toBe(true);
    expect(c.options.plugins.legend.position).toBe("bottom");
  });

  it("Distribution: vertical stacked bars with a Customer / Region / Company Code dropdown (no Mailbox), Duplicates in the legend", async () => {
    signedIn();
    renderApp(fakeDs(), "#/");
    await screen.findByTestId("kpi-total");
    const sel = screen.getByLabelText("Dimension") as HTMLSelectElement;
    expect([...sel.options].map((o) => o.textContent)).toEqual(["Customer", "Region", "Company Code"]);
    const c = lastOf("bar", (p) => p.options?.indexAxis !== "y");
    expect(c.data.datasets.map((d: Props) => [d.label, d.backgroundColor])).toEqual([["Auto Processed", "#059669"], ["Manual Processing", "#d97706"], ["Duplicates", "#7c3aed"], ["Exceptions", "#dc2626"]]);
    expect(c.options.scales.x.title.text).toBe("Customer");
    expect(c.options.scales.y.title.text).toBe("Email Count");
    fireEvent.change(sel, { target: { value: "company_code" } });
    expect(lastOf("bar", (p) => p.options?.scales?.x?.title?.text === "Company Code")).toBeTruthy();
  });

  it("Monthly Processing Trend: line chart with Date / Week / Month / Quarter, y = AI Processed (%) 0-100, blue and orange lines", async () => {
    signedIn();
    renderApp(fakeDs(), "#/");
    await screen.findByTestId("kpi-total");
    const sel = screen.getByLabelText("Period") as HTMLSelectElement;
    expect([...sel.options].map((o) => o.textContent)).toEqual(["Date", "Week", "Month", "Quarter"]);
    const c = lastOf("line", () => true);
    expect(c.data.datasets.map((d: Props) => [d.label, d.borderColor])).toEqual([["Remittance AI Processed %", "#3b82f6"], ["PTP AI Processed %", "#ea580c"]]);
    expect(c.options.scales.y.title.text).toBe("AI Processed (%)");
    expect([c.options.scales.y.beginAtZero, c.options.scales.y.max]).toEqual([true, 100]);
    expect(c.data.datasets[0].data).toEqual([33.3]); // 1 of 3 Remittance rows auto-processed in Oct 2026
    fireEvent.change(sel, { target: { value: "week" } });
    expect(lastOf("line", (p) => p.options?.scales?.x?.title?.text === "Week")).toBeTruthy();
  });

  it("writes 'count (pct%)' into the Performance Stability segments and counts into the Distribution segments", () => {
    const texts: string[] = [];
    const ctx = { save() {}, restore() {}, measureText: () => ({ width: 30 }), fillText: (t: string) => texts.push(t), font: "", fillStyle: "", textAlign: "", textBaseline: "" };
    const bars = (props: Record<string, number>[]) => props.map((p) => ({ getProps: () => p }));
    const chart = {
      ctx,
      data: { datasets: [{ data: [3, 1] }, { data: [1, 0] }] },
      getDatasetMeta: (i: number) => ({ data: bars(i === 0 ? [{ x: 200, base: 0, y: 10 }, { x: 80, base: 0, y: 40 }] : [{ x: 300, base: 200, y: 10 }, { x: 80, base: 80, y: 40 }]) }),
    };
    performanceLabels([4, 1]).afterDatasetsDraw!(chart as never, {} as never, {} as never, {} as never);
    expect(texts).toEqual(["3 (75%)", "1 (100%)", "1 (25%)"]);
    texts.length = 0;
    const vchart = { ctx, data: { datasets: [{ data: [5, 0] }] }, getDatasetMeta: () => ({ data: bars([{ x: 50, y: 20, base: 120 }, { x: 150, y: 100, base: 100 }]) }) };
    stackLabels.afterDatasetsDraw!(vchart as never, {} as never, {} as never, {} as never);
    expect(texts).toEqual(["5"]);
  });
});

describe("Record detail pop-up", () => {
  const open = async () => {
    signedIn();
    const view = renderApp(fakeDs({ workItem: async () => detail() }), "#/queue?record=ENT-000001");
    await screen.findByRole("dialog", { name: "Record Detail" });
    await screen.findByText(/SAP BSID Match/);
    return view;
  };

  it("has the sections in the agreed order, with the AI Explanation and the Actions at the very end", async () => {
    const view = await open();
    const order = [...view.container.querySelectorAll("[data-section]")].map((e) => e.getAttribute("data-section"));
    expect(order).toEqual(["email", "extracted", "viewer", "bsid", "confidence", "pipeline", "audit", "explanation", "actions"]);
  });

  it("SAP BSID Match block shows the eight fields", async () => {
    const view = await open();
    const block = view.container.querySelector('[data-section="bsid"]') as HTMLElement;
    for (const label of ["BSID Invoice", "BSID Customer", "BSID Company Code", "BSID Amount", "BSID Currency", "BSID Posting Date", "Open Item Status", "Amount Difference"]) expect(within(block).getByText(label)).toBeInTheDocument();
    expect(within(block).getByText("BSID match: Yes")).toBeInTheDocument();
    expect(within(block).getByText("Innova Care Products (100001)")).toBeInTheDocument();
    expect(within(block).getByText("0.241%")).toBeInTheDocument();
  });

  it("Confidence Scoring: fast-path banner, five rows with weight, percentage and GREEN bar, final score with badge", async () => {
    const view = await open();
    const block = view.container.querySelector('[data-section="confidence"]') as HTMLElement;
    expect(within(block).getByText(/score set to at least 92 %/)).toBeInTheDocument();
    const rows = block.querySelectorAll(".conf-component");
    expect(rows.length).toBe(5);
    expect([...rows].map((r) => r.querySelector(".comp-weight")!.textContent)).toEqual(["Weight 35%", "Weight 30%", "Weight 10%", "Weight 5%", "Weight 10%"]);
    expect([...rows].every((r) => (r.querySelector(".conf-component-bar-fill") as HTMLElement).style.background.replace(/\s/g, "") === "rgb(5,150,105)")).toBe(true);
    expect(within(block).getByText("Invoice Number Match (EXACT)")).toBeInTheDocument();
    expect(within(block).getByText("Final Confidence Score")).toBeInTheDocument();
    expect(within(block).getByText("High")).toBeInTheDocument();
    expect(within(block).getByText("95.3%", { selector: "span" })).toBeInTheDocument();
  });

  it("AI Explanation is plain-language text built from the scores", async () => {
    const view = await open();
    const block = view.container.querySelector('[data-section="explanation"]') as HTMLElement;
    expect(block.textContent).toMatch(/read as a remittance from Innova Care/);
    expect(block.textContent).toMatch(/matches an open SAP item exactly/);
    expect(block.textContent).toMatch(/95\.3 % \(high\)/);
  });
});

describe("BSID candidates are not shown in the pop-up", () => {
  const open = async (d = detail()) => {
    signedIn();
    const view = renderApp(fakeDs({ workItem: async () => d }), "#/queue?record=ENT-000001");
    await screen.findByText(/SAP BSID Match/);
    return view;
  };

  it("has no BSID Candidates table, although the API still sends the candidates", async () => {
    const d = detail();
    expect(d.candidates.length).toBeGreaterThan(0);
    const view = await open(d);
    expect(view.container.textContent).not.toMatch(/BSID Candidates/);
    expect(view.container.querySelector('[data-section="candidates"]')).toBeNull();
    expect(screen.getByRole("dialog", { name: "Record Detail" }).querySelectorAll("table").length).toBe(0); // (the queue table behind the pop-up is not part of it)
  });

  it("shows one line under the SAP BSID Match block when several open items share the invoice number", async () => {
    const d = detail();
    const view = await open({ ...d, bsid: { ...d.bsid!, shared_invoice_count: 3 } });
    const note = screen.getByTestId("bsid-shared-note");
    expect(note.textContent).toBe("ℹ️ 3 open BSID items share invoice number INV-1. The best match was chosen by amount and currency.");
    const block = view.container.querySelector('[data-section="bsid"]') as HTMLElement;
    expect(block.contains(note)).toBe(true);
  });

  it("shows nothing for a single item or when the count is missing (older API)", async () => {
    const d = detail();
    await open({ ...d, bsid: { ...d.bsid!, shared_invoice_count: 1 } });
    expect(screen.queryByTestId("bsid-shared-note")).not.toBeInTheDocument();
    cleanup();
    await open(d);
    expect(screen.queryByTestId("bsid-shared-note")).not.toBeInTheDocument();
  });
});

describe("explanation rules", () => {
  it("91 % fast path when the amount is missing, none when no fast path applied", () => {
    const d = detail();
    expect(fastPathBanner(d)).toMatch(/at least 92 %/);
    expect(fastPathBanner({ ...d, score_breakdown: { ...d.score_breakdown, fast_path_override: "EXACT_AMOUNT_MISSING" } })).toMatch(/at least 91 %/);
    expect(fastPathBanner({ ...d, score_breakdown: { ...d.score_breakdown, fast_path_override: null } })).toBeNull();
  });

  it("badges: High from 80, Medium from 40, else Low; NEAR and NONE are explained", () => {
    const d = detail();
    const withConf = (c: number) => ({ ...d, score_breakdown: { ...d.score_breakdown, confidence_score: c } });
    expect([confidenceBadge(withConf(83.7)).label, confidenceBadge(withConf(56.4)).label, confidenceBadge(withConf(12)).label]).toEqual(["High", "Medium", "Low"]);
    expect(confidenceRows({ ...d, match_level: "NEAR" })[0].description).toMatch(/OCR/);
    expect(confidenceRows({ ...d, match_level: "NONE", invoice_ref: "X1" })[0].description).toMatch(/matches no open BSID/);
    expect(aiExplanation({ ...d, status: "EXCEPTION", exception_reason: "No BSID match found", bsid: { matched: false } }).join(" ")).toMatch(/exception: No BSID match found/);
  });
});

describe("Exported cases button and the renamed action", () => {
  it("shows 'Exported cases (n)' at the top right of the Action Queue and opens the Excel view", async () => {
    signedIn();
    const workItems = vi.fn(async (p: { status?: string }) => ({ total: p.status === "CONFIRMED" ? 4 : 1, page: 1, page_size: 25, items: p.status === "CONFIRMED" ? [] : [row()] }));
    renderApp(fakeDs({ workItems }), "#/queue");
    const button = await screen.findByTestId("exported-cases-button");
    await waitFor(() => expect(button).toHaveTextContent("Exported cases (4)"));
    fireEvent.click(button);
    const dlg = await screen.findByRole("dialog", { name: "Exported cases" });
    expect(dlg).toHaveTextContent("Download .xlsx");
    expect(await within(dlg).findByText(/No confirmed cases yet/)).toBeInTheDocument();
  });

  it("calls the button 'Confirm & Add to Excel' and never 'Extract' or 'Update SAP'", () => {
    expect(ACTION_LABELS.CONFIRM_ADD_EXCEL).toBe("Confirm & Add to Excel");
    expect(Object.values(ACTION_LABELS).join(" ")).not.toMatch(/Extract|Update SAP/);
    expect(JSON.stringify(sections)).not.toMatch(/Extract to Excel|Update SAP/);
  });
});
