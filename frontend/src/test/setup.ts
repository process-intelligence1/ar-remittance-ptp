import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { vi } from "vitest";

// jsdom cannot draw on a canvas: the charts are replaced by plain boxes that carry their data labels
vi.mock("react-chartjs-2", () => {
  const box = (kind: string) => (props: { data?: { labels?: unknown[] } }) =>
    createElement("div", { "data-chart": kind, "data-points": props.data?.labels?.length ?? 0 });
  return { Bar: box("bar"), Line: box("line") };
});
