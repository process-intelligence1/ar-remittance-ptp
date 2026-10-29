import { useMemo, useState } from "react";
import sections from "../kb/sections.json";

interface Section {
  id: string;
  title: string;
  html: string;
}

const NAV_TITLES: Record<string, string> = {
  flow: "End-to-End Flow",
  bsid: "BSID Validation",
  duplicates: "Duplicate Detection",
  ptp: "Promise-to-Pay Handling",
  oos: "Out-of-Scope Handling",
  scoring: "Confidence Scoring",
  example: "Example Calculation",
};

const plain = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").toLowerCase();

/** The Knowledge Base. Its content is generated from the prototype (docs/prototype) with the agreed changes:
 *  "Invoice Number Match" (EXACT / NEAR / NONE), the recalculated worked example, "Confirm & Extract to Excel". */
export default function KnowledgeBase() {
  const all = sections as Section[];
  const [active, setActive] = useState(all[0].id);
  const [search, setSearch] = useState("");
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    return new Set(all.filter((s) => !q || plain(s.html).includes(q) || s.title.toLowerCase().includes(q)).map((s) => s.id));
  }, [all, search]);
  const current = all.find((s) => s.id === active && matches.has(s.id)) ?? all.find((s) => matches.has(s.id));

  return (
    <div className="page active" id="page-kb">
      <div className="page-content">
        <div className="page-header">
          <h1>📚 Knowledge Base</h1>
          <p>How the AR Remittance &amp; PTP Processing System Works</p>
        </div>
        <div className="kb-grid">
          <div className="kb-nav">
            {all.map((s) => (
              <div key={s.id} className={`kb-nav-item${current?.id === s.id ? " active" : ""}${matches.has(s.id) ? "" : " hidden-by-search"}`} onClick={() => setActive(s.id)}>
                {NAV_TITLES[s.id] ?? s.title}
              </div>
            ))}
          </div>
          <div className="kb-content">
            <div className="kb-toolbar">
              <input className="kb-search" type="text" placeholder="🔍 Search the Knowledge Base..." aria-label="Search the Knowledge Base" value={search} onChange={(e) => setSearch(e.target.value)} />
              <span className="kb-progress">{matches.size} of {all.length} topics</span>
            </div>
            {current ? (
              <div className="kb-section active" dangerouslySetInnerHTML={{ __html: current.html }} />
            ) : (
              <div className="empty-state">No topic matches "{search}".</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
