import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { waitForServer, type ServerState } from "../auth/warmup";
import type { DataSource } from "../data";
import { evidenceBoxes } from "../data/evidence";
import { LiveDataSource, toQuery } from "../data/live";
import { ACTION_LABELS } from "../data/labels";
import sections from "../kb/sections.json";
import { SLOW_TEXT, STARTING_TEXT } from "../pages/Login";
import { fakeDs, renderApp, row, signedIn, USERS } from "./helpers";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe("server warm-up", () => {
  it("keeps asking /api/health until the server answers, then reports ready", async () => {
    let calls = 0;
    const ds = fakeDs({ health: async () => ++calls >= 3 });
    const states: ServerState[] = [];
    const ok = await waitForServer(ds, { onState: (s) => states.push(s), sleep: async () => {} });
    expect(ok).toBe(true);
    expect(calls).toBe(3);
    expect(states[0]).toBe("starting");
    expect(states.at(-1)).toBe("ready");
  });

  it("says 'slow' after 1 minute but keeps trying", async () => {
    let t = 0;
    let calls = 0;
    const states: ServerState[] = [];
    const ds = fakeDs({ health: async () => ++calls > 40 });
    await waitForServer(ds, { onState: (s) => states.push(s), now: () => t, sleep: async () => { t += 3000; } });
    expect(states).toContain("slow");
    expect(states.at(-1)).toBe("ready");
  });
});

describe("login screen", () => {
  it("wakes the API as soon as it opens and shows the starting message until it answers", async () => {
    let answer: (v: boolean) => void = () => {};
    const health = vi.fn(() => new Promise<boolean>((r) => { answer = r; }));
    renderApp(fakeDs({ health }), "#/login");
    expect(health).toHaveBeenCalledTimes(1); // called on open, in the background
    expect(screen.getByText(STARTING_TEXT)).toBeInTheDocument();
    expect(screen.getByLabelText("Access code")).toBeDisabled();
    await act(async () => answer(true));
    expect(await screen.findByText("Server ready")).toBeInTheDocument();
    expect(screen.queryByText(STARTING_TEXT)).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Access code")).toBeEnabled());
    expect(await screen.findByText(/Asha \(AR Analyst\)/)).toBeInTheDocument();
  });

  it("shows the long-wait message after 1 minute, with a Retry button that starts the wait again", async () => {
    vi.useFakeTimers();
    const health = vi.fn(async () => false);
    renderApp(fakeDs({ health }), "#/login");
    await act(async () => { await vi.advanceTimersByTimeAsync(50_000); });
    expect(screen.getByText(STARTING_TEXT)).toBeInTheDocument(); // not yet
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(screen.getByText(SLOW_TEXT)).toBeInTheDocument();
    const calls = health.mock.calls.length;
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Retry" })); });
    expect(screen.getByText(STARTING_TEXT)).toBeInTheDocument();
    expect(health.mock.calls.length).toBeGreaterThan(calls); // asks the server again at once
  });

  it("uses the agreed texts", () => {
    expect(STARTING_TEXT).toBe("Starting the server... this can take up to 1 minute after a quiet period");
    expect(SLOW_TEXT).toBe("Still starting - please wait or click Retry");
  });

  it("signs in and opens the Dashboard; a wrong code shows the error and clears the field", async () => {
    const login = vi.fn().mockRejectedValueOnce(new Error("Wrong user or access code.")).mockImplementation(async (u: string) => ({ token: "t", expires_at: new Date(Date.now() + 3600e3).toISOString(), user: USERS.find((x) => x.email === u)! }));
    renderApp(fakeDs({ login }), "#/login");
    const code = await screen.findByLabelText("Access code");
    await waitFor(() => expect(code).toBeEnabled());
    fireEvent.change(code, { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong user or access code.");
    expect(code).toHaveValue("");
    fireEvent.change(code, { target: { value: "good" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Total Processed", { exact: false })).toBeInTheDocument();
  });

  it("after Azure ends (VITE_LIVE_ENDED) it shows the ended page with a link, and never calls the server", () => {
    vi.stubEnv("VITE_LIVE_ENDED", "true");
    const health = vi.fn(async () => true);
    renderApp(fakeDs({ health }), "#/login");
    expect(screen.getByText("The live system has ended")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /demo edition/i })).toHaveAttribute("href");
    expect(health).not.toHaveBeenCalled();
  });
});

describe("sign-in when the server cannot be reached", () => {
  it("shows a clear message instead of 'Failed to fetch', waits for the server again, and keeps the typed code", async () => {
    const { NetworkError } = await import("../data");
    const login = vi.fn().mockRejectedValue(new NetworkError("Could not reach the server - it may be restarting. Please wait a moment and try again."));
    const health = vi.fn(async () => true);
    renderApp(fakeDs({ login, health }), "#/login");
    const code = await screen.findByLabelText("Access code");
    await waitFor(() => expect(code).toBeEnabled());
    fireEvent.change(code, { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByRole("alert")).not.toHaveTextContent("Failed to fetch");
    await waitFor(() => expect(health.mock.calls.length).toBeGreaterThan(1)); // the wake-up check ran again
    expect(code).toHaveValue("abc");
  });
});

describe("data layer", () => {
  it("builds query strings without empty values", () => {
    expect(toQuery({ a: "x y", b: "", c: undefined, d: 0 })).toBe("?a=x+y&d=0");
  });

  it("sends the token, and a 401 signs the user out", async () => {
    const calls: Request[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      calls.push(new Request("http://x" + url, init));
      return new Response(JSON.stringify({ detail: "Token expired" }), { status: 401 });
    }));
    const ds = new LiveDataSource("");
    const out = vi.fn();
    ds.onUnauthorized(out);
    ds.setToken("abc");
    await expect(ds.workItems({ page: 2 })).rejects.toThrow();
    expect(calls[0].headers.get("Authorization")).toBe("Bearer abc");
    expect(calls[0].url).toContain("/api/work-items?page=2");
    expect(out).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("turns a failed fetch (server unreachable) into a clear NetworkError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(new LiveDataSource("https://api.example").login("a@b.c", "x")).rejects.toThrow(/Could not reach the server/);
    vi.unstubAllGlobals();
  });

  it("turns relative signed links into API links", () => {
    expect(new LiveDataSource("https://api.example").resolveUrl("/api/attachments/1/file?token=t")).toBe("https://api.example/api/attachments/1/file?token=t");
    expect(new LiveDataSource("https://api.example").resolveUrl("https://other/x")).toBe("https://other/x");
  });

  it("finds highlighted values (bbox + page + attachment) in the evidence JSON", () => {
    const boxes = evidenceBoxes({ best: { ref: { bbox: [0.1, 0.2, 0.3, 0.4], page: 1, text: "INV-1", source: "att:35" }, amount: { bbox: [0.5, 0.2, 0.7, 0.4], page: 2, text: "12.50", source: "att:35" }, row: "x" }, also_found: [{ amount: "1", source: "att:35" }] });
    expect(boxes.map((b) => [b.attachmentId, b.page, b.label])).toEqual([[35, 1, "ref"], [35, 2, "amount"]]);
    expect(evidenceBoxes(null)).toEqual([]);
  });
});

describe("Action Queue", () => {
  it("shows Match_Field and Match_Level columns, no mailbox filter, and company codes 1000-6000", async () => {
    signedIn();
    renderApp(fakeDs(), "#/queue");
    expect(await screen.findByText("ENT-000001")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Match_Field" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Match_Level" })).toBeInTheDocument();
    expect(screen.queryByText(/mailbox/i)).not.toBeInTheDocument();
    const co = screen.getByLabelText("Company Code");
    expect(within(co).getAllByRole("option").map((o) => o.textContent)).toEqual(["All Company Codes", "1000", "2000", "3000", "4000", "5000", "6000"]);
  });

  it("offers only the bulk actions valid for every selected row, labelled 'Confirm & Extract to Excel (n)'", async () => {
    signedIn();
    const a = row({ id: 1, entry_id: "ENT-000001", allowed_actions: ["CONFIRM_EXTRACT_EXCEL", "REJECT", "REQUEST_CLARIFICATION"] });
    const b = row({ id: 2, entry_id: "ENT-000002", allowed_actions: ["REJECT", "REQUEST_CLARIFICATION"] });
    renderApp(fakeDs({ rows: [a, b] }), "#/queue");
    await screen.findByText("ENT-000002");
    const bulk = screen.getByLabelText("Bulk action") as HTMLSelectElement;
    expect(bulk).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    expect(within(bulk).getByRole("option", { name: "Confirm & Extract to Excel (1)" })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Select ENT-000002"));
    const names = within(bulk).getAllByRole("option").map((o) => o.textContent);
    expect(names).not.toContain("Confirm & Extract to Excel (2)"); // not valid for row 2
    expect(names).toEqual(expect.arrayContaining(["Reject Record", "Request Clarification"]));
  });

  it("an action tells the user it arrives in M09 (through the data layer)", async () => {
    signedIn();
    const performAction = vi.fn(fakeDs().performAction);
    renderApp(fakeDs({ performAction }), "#/queue");
    await screen.findByText("ENT-000001");
    fireEvent.click(screen.getByLabelText("Select ENT-000001"));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "CONFIRM_EXTRACT_EXCEL" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to Selected" }));
    expect(await screen.findByText(/available in M09/)).toBeInTheDocument();
    expect(performAction).toHaveBeenCalledWith({ action: "CONFIRM_EXTRACT_EXCEL", ids: [1] });
  });

  it("the picked columns are remembered", async () => {
    signedIn();
    renderApp(fakeDs(), "#/queue");
    await screen.findByText("ENT-000001");
    fireEvent.click(screen.getByRole("button", { name: /Columns/ }));
    fireEvent.click(within(document.querySelector(".column-picker-menu") as HTMLElement).getByLabelText("Region"));
    expect(JSON.parse(localStorage.getItem("ar_queue_columns")!).region).toBe(true);
  });
});

describe("Dashboard and live updates", () => {
  it("shows the five KPI cards from the API", async () => {
    signedIn();
    renderApp(fakeDs(), "#/");
    expect(await screen.findByTestId("kpi-total")).toHaveTextContent("3");
    expect(screen.getByTestId("kpi-exceptions")).toHaveTextContent("1");
    expect(screen.queryByText(/mailbox/i)).not.toBeInTheDocument();
  });

  it("polls /api/changes only while the tab is visible and reloads the lists when rows changed", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    signedIn();
    const changes = vi.fn(async () => ({ server_time: "", next_since: "2026-10-12T00:00:00Z", new_work_items: { count: 2, ids: [1, 2] }, updated_work_items: { count: 0, ids: [] }, new_emails: 1, changed: true }));
    const workItems = vi.fn(fakeDs().workItems);
    renderApp(fakeDs({ changes, workItems }), "#/queue");
    await screen.findByText("ENT-000001");
    const before = workItems.mock.calls.length;
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    await act(async () => { await vi.advanceTimersByTimeAsync(40_000); });
    expect(changes).not.toHaveBeenCalled(); // hidden tab: no polling
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    await act(async () => { await vi.advanceTimersByTimeAsync(13_000); }); // next poll is due 11 s later; the toast stays 4.5 s
    expect(changes).toHaveBeenCalled();
    expect(await screen.findByText("2 new records arrived")).toBeInTheDocument();
    expect(workItems.mock.calls.length).toBeGreaterThan(before); // the queue reloaded without a refresh
  });
});

describe("Knowledge Base and wording", () => {
  it("has the Invoice Number Match section and the recalculated worked example", () => {
    const text = JSON.stringify(sections);
    expect(text).toContain("Invoice Number Match");
    for (const v of ["56.4%", "83.7%", "95.3%", "max(fast-path value, formula)"]) expect(text).toContain(v);
    for (const old of ["Update SAP", "Digit Match", "Digit Evidence", "85.34", "mailboxes"]) expect(text).not.toContain(old);
    expect(text).toContain("Confirm &amp; Extract to Excel");
  });

  it("never says 'Confirm & Update SAP' on any button label", () => {
    expect(ACTION_LABELS.CONFIRM_EXTRACT_EXCEL).toBe("Confirm & Extract to Excel");
    expect(Object.values(ACTION_LABELS).join(" ")).not.toMatch(/Update SAP/);
  });

  it("renders the KB page with its topics", async () => {
    signedIn();
    renderApp(fakeDs(), "#/kb");
    expect(await screen.findByText("Example Calculation")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Example Calculation"));
    expect(await screen.findByText(/Exact number: 23756668/)).toBeInTheDocument();
  });
});

it("signing out returns to the login screen", async () => {
  signedIn();
  const ds: DataSource = fakeDs();
  renderApp(ds, "#/");
  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByLabelText("Access code")).toBeInTheDocument();
  expect(sessionStorage.getItem("ar_session")).toBeNull();
});

describe("idle handling", () => {
  it("pauses live updates after 5 minutes without activity, shows 'Paused - click to refresh', and a click resumes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    signedIn();
    const changes = vi.fn(async () => ({ server_time: "", next_since: "2026-10-12T00:00:00Z", new_work_items: { count: 0, ids: [] }, updated_work_items: { count: 0, ids: [] }, new_emails: 0, changed: false }));
    const workItems = vi.fn(fakeDs().workItems);
    renderApp(fakeDs({ changes, workItems }), "#/queue");
    await screen.findByText("ENT-000001");
    expect(screen.queryByText("Paused - click to refresh")).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(5 * 60_000 + 10_000); });
    const banner = await screen.findByText("Paused - click to refresh");
    const callsWhenPaused = changes.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(changes.mock.calls.length).toBe(callsWhenPaused); // no polling while paused
    window.dispatchEvent(new Event("mousemove"));
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(screen.getByText("Paused - click to refresh")).toBeInTheDocument(); // movement alone does not resume
    const before = workItems.mock.calls.length;
    fireEvent.click(banner);
    expect(screen.queryByText("Paused - click to refresh")).not.toBeInTheDocument();
    await waitFor(() => expect(workItems.mock.calls.length).toBeGreaterThan(before)); // refreshed
  });

  it("signs the user out after 60 minutes without activity, with a message", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    signedIn();
    renderApp(fakeDs(), "#/queue");
    await screen.findByText("ENT-000001");
    await act(async () => { await vi.advanceTimersByTimeAsync(59 * 60_000); });
    expect(sessionStorage.getItem("ar_session")).not.toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync(2 * 60_000); });
    expect(await screen.findByText("You were signed out after 60 minutes without activity.")).toBeInTheDocument();
    expect(sessionStorage.getItem("ar_session")).toBeNull();
  });

  it("activity postpones the sign-out", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    signedIn();
    renderApp(fakeDs(), "#/queue");
    await screen.findByText("ENT-000001");
    for (let i = 0; i < 4; i++) {
      await act(async () => { await vi.advanceTimersByTimeAsync(20 * 60_000); });
      window.dispatchEvent(new Event("keydown"));
    }
    expect(sessionStorage.getItem("ar_session")).not.toBeNull(); // 80 minutes passed, never 60 idle
  });
});

describe("routes survive a refresh or a shared link", () => {
  it("a deep link opens the right screen and record, again after a simulated refresh (hash routing, no server routes)", async () => {
    signedIn();
    const detail = vi.fn(async () => { throw new Error("detail not needed"); });
    for (const hash of ["#/audit", "#/kb", "#/queue?record=ENT-000001"]) {
      const view = renderApp(fakeDs({ workItem: detail }), hash); // a fresh page load on that address
      await waitFor(() => expect(view.container.querySelector(hash.includes("audit") ? "#page-audit" : hash.includes("kb") ? "#page-kb" : "#page-queue")).not.toBeNull());
      if (hash.includes("record=")) expect(await screen.findByRole("dialog", { name: "Record Detail" })).toBeInTheDocument();
      view.unmount();
    }
  });

  it("uses hash routes only, so GitHub Pages never needs a server route", () => {
    signedIn();
    renderApp(fakeDs(), "#/queue");
    const link = screen.getByRole("link", { name: /Audit Trail/ });
    expect(link.getAttribute("href")).toBe("#/audit");
  });
});

describe("shared links", () => {
  it("a signed-out visitor of a shared link signs in and lands on that record", async () => {
    const ds = fakeDs({ workItem: async () => { throw new Error("detail not needed"); } });
    renderApp(ds, "#/queue?record=ENT-000001"); // someone opens a shared link without a session
    const code = await screen.findByLabelText("Access code");
    expect(window.location.hash).toContain("/login?next=");
    await waitFor(() => expect(code).toBeEnabled());
    fireEvent.change(code, { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("dialog", { name: "Record Detail" })).toBeInTheDocument();
    expect(window.location.hash).toBe("#/queue?record=ENT-000001");
  });

  it("ignores a next= address that leaves the app", async () => {
    signedIn();
    renderApp(fakeDs(), "#/login?next=//evil.example");
    expect(await screen.findByTestId("kpi-total")).toBeInTheDocument(); // normal landing page
  });
});
