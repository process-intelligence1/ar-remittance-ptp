import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { beforeEach, vi } from "vitest";

// jsdom cannot draw on a canvas: the charts are replaced by plain boxes. Their props (data, options, plugins) are kept in
// globalThis.__chartProps so tests can check the chart configuration.
type Store = { __chartProps: Record<string, unknown>[] };
(globalThis as unknown as Store).__chartProps = [];
beforeEach(() => {
  (globalThis as unknown as Store).__chartProps.length = 0;
});
vi.mock("react-chartjs-2", () => {
  const box = (kind: string) => (props: { data?: { labels?: unknown[] } }) => {
    (globalThis as unknown as Store).__chartProps.push({ kind, ...props });
    return createElement("div", { "data-chart": kind, "data-points": props.data?.labels?.length ?? 0 });
  };
  return { Bar: box("bar"), Line: box("line") };
});
