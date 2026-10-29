import { useCallback, useEffect, useRef, useState } from "react";

export const PAUSE_AFTER_MS = 5 * 60_000; // live updates pause after 5 minutes without activity
export const LOGOUT_AFTER_MS = 60 * 60_000; // automatic sign-out after 60 minutes without activity
const CHECK_MS = 5_000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "wheel"] as const;

/** Tracks user activity. After `pauseAfterMs` without any, `paused` becomes true (the app stops polling; only a click on
 *  the "Paused - click to refresh" banner resumes). After `logoutAfterMs` without activity `onLogout` is called. */
export function useIdle(enabled: boolean, onLogout: () => void, opts: { pauseAfterMs?: number; logoutAfterMs?: number } = {}) {
  const { pauseAfterMs = PAUSE_AFTER_MS, logoutAfterMs = LOGOUT_AFTER_MS } = opts;
  const [paused, setPaused] = useState(false);
  const last = useRef(Date.now());
  const logoutRef = useRef(onLogout);
  logoutRef.current = onLogout;

  const resume = useCallback(() => {
    last.current = Date.now();
    setPaused(false);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    last.current = Date.now();
    setPaused(false);
    const touch = () => {
      last.current = Date.now(); // activity keeps the sign-out clock running from zero; it does not un-pause
    };
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, touch, { passive: true }));
    const timer = setInterval(() => {
      const idle = Date.now() - last.current;
      if (idle >= logoutAfterMs) logoutRef.current();
      else if (idle >= pauseAfterMs) setPaused(true);
    }, CHECK_MS);
    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, touch));
      clearInterval(timer);
    };
  }, [enabled, pauseAfterMs, logoutAfterMs]);

  return { paused, resume };
}
