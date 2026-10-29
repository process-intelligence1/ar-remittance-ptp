import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import type { Filters } from "../data";
import { CLASS_LABELS, COMPANY_CODES, STATUS_LABELS } from "../data/labels";

const SHOWN_CLASSES = ["REMITTANCE", "PTP", "DUPLICATE", "EXCEPTION", "OUT_OF_SCOPE"];

/** Filter bar shared by the Dashboard and the Action Queue (no mailbox filter: there is one inbox). */
export default function FilterBar({
  value,
  onChange,
  extra,
}: {
  value: Filters;
  onChange: (f: Filters) => void;
  extra?: "queue" | "dashboard";
}) {
  const { ds } = useAuth();
  // region options come from the data itself (BSID XREF2)
  const facets = useQuery({ queryKey: ["kpis", "facets"], queryFn: () => ds.kpis({}), staleTime: 60_000 });
  const regions = (facets.data?.distributions.region ?? []).map((r) => r.label).filter((l) => l !== "(none)");
  const set = (patch: Partial<Filters>) => {
    const next = { ...value, ...patch };
    (Object.keys(next) as (keyof Filters)[]).forEach((k) => {
      if (next[k] === "" || next[k] === undefined) delete next[k];
    });
    onChange(next);
  };
  return (
    <div className="filters-bar">
      <div className="filters-bar-header">
        <h3>🔽 Filters</h3>
        <button className="filter-btn btn-reset" onClick={() => onChange({})}>
          Reset Filters
        </button>
      </div>
      <div className="filters-row">
        {extra === "queue" && (
          <div className="filter-group">
            <label htmlFor="f-q">Search</label>
            <input id="f-q" type="text" placeholder="Entry ID, invoice, customer…" value={value.q ?? ""} onChange={(e) => set({ q: e.target.value })} />
          </div>
        )}
        <div className="filter-group">
          <label htmlFor="f-from">From Date</label>
          <input id="f-from" type="date" value={value.from_date ?? ""} onChange={(e) => set({ from_date: e.target.value })} />
        </div>
        <div className="filter-group">
          <label htmlFor="f-to">To Date</label>
          <input id="f-to" type="date" value={value.to_date ?? ""} onChange={(e) => set({ to_date: e.target.value })} />
        </div>
        <div className="filter-group">
          <label htmlFor="f-customer">Customer</label>
          <input id="f-customer" type="text" placeholder="Name or number" value={value.customer ?? ""} onChange={(e) => set({ customer: e.target.value })} />
        </div>
        <div className="filter-group">
          <label htmlFor="f-region">Region</label>
          <select id="f-region" value={value.region ?? ""} onChange={(e) => set({ region: e.target.value })}>
            <option value="">All Regions</option>
            {regions.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="f-co">Company Code</label>
          <select id="f-co" value={value.company_code ?? ""} onChange={(e) => set({ company_code: e.target.value })}>
            <option value="">All Company Codes</option>
            {COMPANY_CODES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="f-status">Status</label>
          <select id="f-status" value={value.status ?? ""} onChange={(e) => set({ status: e.target.value })}>
            <option value="">All Statuses</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="f-cls">Classification</label>
          <select id="f-cls" value={value.classification ?? ""} onChange={(e) => set({ classification: e.target.value })}>
            <option value="">All</option>
            {SHOWN_CLASSES.map((c) => (
              <option key={c} value={c}>
                {CLASS_LABELS[c]}
              </option>
            ))}
          </select>
        </div>
        {extra === "queue" && (
          <>
            <div className="filter-group">
              <label htmlFor="f-bsid">BSID Match</label>
              <select id="f-bsid" value={value.bsid_match ?? ""} onChange={(e) => set({ bsid_match: e.target.value as Filters["bsid_match"] })}>
                <option value="">All</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
            <div className="filter-group">
              <label htmlFor="f-conf">Confidence</label>
              <select
                id="f-conf"
                value={`${value.min_confidence ?? ""}-${value.max_confidence ?? ""}`}
                onChange={(e) => {
                  const [min, max] = e.target.value.split("-");
                  set({ min_confidence: min === "" ? undefined : Number(min), max_confidence: max === "" ? undefined : Number(max) });
                }}
              >
                <option value="-">All</option>
                <option value="80-">High (≥ 80%)</option>
                <option value="40-79.99">Medium (40–79%)</option>
                <option value="-39.99">Low (&lt; 40%)</option>
              </select>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
