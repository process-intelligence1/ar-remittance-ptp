import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import type { DataSource } from "../data";

export const POLL_MS = 17000; // 15-20 s, only while the tab is visible

/** Polls /api/changes while the tab is visible; when rows changed, the lists and the Dashboard reload. */
export function useChanges(ds: DataSource, enabled: boolean, onNew: (n: number) => void, intervalMs = POLL_MS) {
  const qc = useQueryClient();
  const cursor = useRef<string>("2100-01-01T00:00:00Z"); // the first poll only learns the server time (no client clock needed)
  const onNewRef = useRef(onNew);
  onNewRef.current = onNew;

  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const tick = async () => {
      if (stopped || document.visibilityState !== "visible") return schedule();
      try {
        const c = await ds.changes(cursor.current);
        cursor.current = c.next_since;
        if (c.changed) {
          await qc.invalidateQueries({ queryKey: ["workItems"] });
          await qc.invalidateQueries({ queryKey: ["kpis"] });
          await qc.invalidateQueries({ queryKey: ["audit"] });
          await qc.invalidateQueries({ queryKey: ["workItem"] });
          if (c.new_work_items.count > 0) onNewRef.current(c.new_work_items.count);
        }
      } catch {
        /* a failed poll is simply tried again later (401 is handled by the data source) */
      }
      schedule();
    };
    const schedule = () => {
      if (!stopped) timer = setTimeout(tick, intervalMs);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible" && !stopped) {
        clearTimeout(timer);
        timer = setTimeout(tick, 500); // catch up right after the tab comes back
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    schedule();
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [ds, enabled, qc, intervalMs]);
}
