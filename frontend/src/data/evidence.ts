import type { EvidenceBox } from "./types";

/** Finds every highlighted value in the evidence JSON of a work item: objects that carry a page position
 *  (bbox as fractions of the page), the page and the attachment ("att:<id>") they were read from. */
export function evidenceBoxes(evidence: unknown): EvidenceBox[] {
  const found: EvidenceBox[] = [];
  const seen = new Set<string>();
  const walk = (node: unknown, key: string) => {
    if (Array.isArray(node)) return node.forEach((n) => walk(n, key));
    if (!node || typeof node !== "object") return;
    const o = node as Record<string, unknown>;
    const bbox = o.bbox;
    const source = typeof o.source === "string" ? /^att:(\d+)$/.exec(o.source) : null;
    if (Array.isArray(bbox) && bbox.length === 4 && bbox.every((n) => typeof n === "number") && source) {
      const page = typeof o.page === "number" ? o.page : 1;
      const id = `${source[1]}|${page}|${bbox.join(",")}`;
      if (!seen.has(id)) {
        seen.add(id);
        found.push({ attachmentId: Number(source[1]), page, bbox: bbox as EvidenceBox["bbox"], label: key, text: typeof o.text === "string" ? o.text : "" });
      }
    }
    for (const [k, v] of Object.entries(o)) walk(v, k);
  };
  walk(evidence, "value");
  return found;
}
