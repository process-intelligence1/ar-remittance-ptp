import { LiveDataSource } from "./live";
import { SnapshotDataSource } from "./snapshot";
import type { DataSource } from "./types";

export * from "./types";

/** The data source chosen at build time: VITE_DATA_SOURCE=live (default) or snapshot. */
export function createDataSource(): DataSource {
  if (import.meta.env.VITE_DATA_SOURCE === "snapshot") return new SnapshotDataSource();
  return new LiveDataSource(import.meta.env.VITE_API_URL ?? "");
}
