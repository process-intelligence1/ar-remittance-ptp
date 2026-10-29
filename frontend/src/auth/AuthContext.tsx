import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { DataSource, Session } from "../data";

const KEY = "ar_session";

function load(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return new Date(s.expires_at).getTime() > Date.now() ? s : null;
  } catch {
    return null;
  }
}

interface AuthValue {
  session: Session | null;
  expiredMessage: string | null;
  login: (user: string, accessCode: string) => Promise<void>;
  logout: (message?: string) => void;
  ds: DataSource;
}

const Ctx = createContext<AuthValue | null>(null);

export function AuthProvider({ ds, children }: { ds: DataSource; children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const s = load();
    ds.setToken(s?.token ?? null);
    return s;
  });
  const [expiredMessage, setExpired] = useState<string | null>(null);

  const clear = useCallback(
    (message: string | null) => {
      ds.setToken(null);
      try {
        sessionStorage.removeItem(KEY);
      } catch {
        /* private mode: nothing to clear */
      }
      setSession(null);
      setExpired(message);
    },
    [ds],
  );

  useEffect(() => {
    ds.onUnauthorized(() => clear("Your session has expired - please sign in again."));
  }, [ds, clear]);

  const login = useCallback(
    async (user: string, accessCode: string) => {
      const s = await ds.login(user, accessCode);
      ds.setToken(s.token);
      try {
        sessionStorage.setItem(KEY, JSON.stringify(s));
      } catch {
        /* the session then lasts until reload */
      }
      setExpired(null);
      setSession(s);
    },
    [ds],
  );

  const value = useMemo(() => ({ session, expiredMessage, login, logout: (message?: string) => clear(message ?? null), ds }), [session, expiredMessage, login, clear, ds]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
