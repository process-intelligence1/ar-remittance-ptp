import type { DataSource } from "../data";

export type ServerState = "starting" | "ready" | "slow";

export interface WarmupOptions {
  intervalMs?: number;
  slowAfterMs?: number;
  attemptTimeoutMs?: number;
  signal?: AbortSignal;
  onState: (state: ServerState) => void;
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
}

/** Calls /api/health until the server answers. After idle the API container needs up to ~30 s to start;
 *  after slowAfterMs (1 minute) the state becomes "slow" (and keeps trying). Resolves when the server is ready. */
export async function waitForServer(ds: DataSource, opts: WarmupOptions): Promise<boolean> {
  const { intervalMs = 3000, slowAfterMs = 60000, attemptTimeoutMs = 10000, signal, onState } = opts;
  const now = opts.now ?? Date.now;
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  const started = now();
  onState("starting");
  while (!signal?.aborted) {
    const attempt = new AbortController();
    const timer = setTimeout(() => attempt.abort(), attemptTimeoutMs);
    const ok = await ds.health(attempt.signal).catch(() => false);
    clearTimeout(timer);
    if (ok) {
      onState("ready");
      return true;
    }
    if (now() - started >= slowAfterMs) onState("slow");
    await sleep(intervalMs);
  }
  return false;
}
