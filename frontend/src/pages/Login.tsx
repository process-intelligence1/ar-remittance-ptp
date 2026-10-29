import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { waitForServer, type ServerState } from "../auth/warmup";
import type { DemoUser } from "../data";
import { ROLE_LABELS } from "../data/labels";

export const STARTING_TEXT = "Starting the server... this can take up to 1 minute after a quiet period";
export const SLOW_TEXT = "Still starting - please wait or click Retry";

export function LiveEnded() {
  const demoUrl = new URL("../", window.location.origin + import.meta.env.BASE_URL).toString();
  return (
    <div className="page-content">
      <div className="login-card ended-card">
        <h1>The live system has ended</h1>
        <p className="sub">The cloud environment behind this edition is no longer running.</p>
        <p>Use the demo edition instead - it has the same screens with a saved set of data.</p>
        <a href={demoUrl}>Open the demo edition</a>
      </div>
    </div>
  );
}

export default function Login() {
  const { ds, session, login, expiredMessage } = useAuth();
  const [state, setState] = useState<ServerState>("starting");
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [user, setUser] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0); // "Retry" starts the wait again
  const loaded = useRef(false);
  const [params] = useSearchParams();
  const next = params.get("next");
  const target = next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") ? next : "/"; // in-app addresses only
  const ended = import.meta.env.VITE_LIVE_ENDED === "true";

  // As soon as the screen opens: wake the API in the background (it sleeps when idle).
  useEffect(() => {
    if (ended) return;
    const ctl = new AbortController();
    void waitForServer(ds, { signal: ctl.signal, onState: setState });
    return () => ctl.abort();
  }, [ds, ended, attempt]);

  useEffect(() => {
    if (state !== "ready" || loaded.current) return;
    loaded.current = true;
    ds.demoUsers()
      .then((u) => {
        setUsers(u);
        setUser(u[0]?.email ?? "");
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, [state, ds]);

  if (ended) return <LiveEnded />;
  if (session) return <Navigate to={target} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(user, code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  const ready = state === "ready";
  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit} aria-label="Sign in">
        <h1>AR Remittance &amp; PTP Processing</h1>
        <div className="sub">Sign in with a demo user and the demo access code.</div>
        {ready ? (
          <div className="server-status ready" role="status">
            Server ready
          </div>
        ) : (
          <div className={`server-status ${state}`} role="status">
            <span className="spinner" aria-hidden="true" />
            {state === "slow" ? SLOW_TEXT : STARTING_TEXT}
            {state === "slow" && (
              <button type="button" onClick={() => { setState("starting"); setAttempt((n) => n + 1); }} style={{ marginLeft: "auto" }}>
                Retry
              </button>
            )}
          </div>
        )}
        {expiredMessage && <div className="error-text">{expiredMessage}</div>}
        <label htmlFor="demo-user">Demo user</label>
        <select id="demo-user" value={user} onChange={(e) => setUser(e.target.value)} disabled={!ready || busy}>
          {users.map((u) => (
            <option key={u.email} value={u.email}>
              {u.name} - {ROLE_LABELS[u.role] ?? u.role}
            </option>
          ))}
        </select>
        <label htmlFor="access-code">Access code</label>
        <input id="access-code" type="password" autoComplete="off" value={code} onChange={(e) => setCode(e.target.value)} disabled={!ready || busy} />
        <button className="primary" type="submit" disabled={!ready || busy || !code || !user}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {error && (
          <div className="error-text" role="alert">
            {error}
          </div>
        )}
      </form>
    </div>
  );
}
