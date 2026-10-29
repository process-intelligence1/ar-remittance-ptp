import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { HashRouter, NavLink, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ToastProvider, useToast } from "./components/Toasts";
import { createDataSource, type DataSource } from "./data";
import { ROLE_LABELS } from "./data/labels";
import { useChanges } from "./hooks/useChanges";
import { useIdle } from "./hooks/useIdle";
import Audit from "./pages/Audit";
import Dashboard from "./pages/Dashboard";
import DemoControl from "./pages/DemoControl";
import KnowledgeBase from "./pages/KnowledgeBase";
import Login from "./pages/Login";
import Queue from "./pages/Queue";

function Layout() {
  const { session, logout, ds } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const location = useLocation();
  // no activity for 5 minutes: live updates pause; after 60 minutes the user is signed out
  const { paused, resume } = useIdle(!!session, () => logout("You were signed out after 60 minutes without activity."));
  useChanges(ds, !!session && ds.kind === "live" && !paused, (n) => toast(`${n} new record${n === 1 ? "" : "s"} arrived`, "info"));
  const refresh = () => {
    resume();
    for (const key of ["workItems", "kpis", "audit", "workItem"]) void qc.invalidateQueries({ queryKey: [key] });
  };
  const total = useQuery({
    queryKey: ["workItems", "count"],
    queryFn: () => ds.workItems({ page_size: 1 }),
    enabled: !!session,
  });
  // signed out: go to the login screen and come back to this exact address afterwards (shared links, F5)
  if (!session) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return (
    <>
      <div id="topbar">
        <div className="logo">
          <div className="logo-icon">AR</div>
          <div>
            AR
            <span className="logo-sub">Remittance &amp; PTP Processing</span>
          </div>
        </div>
        <nav id="nav">
          <NavLink to="/" end className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>
            <span className="nav-icon">📊</span> Dashboard
          </NavLink>
          <NavLink to="/queue" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>
            <span className="nav-icon">⚡</span> Action Queue
            <span className="acc-count">{total.data?.total ?? "—"}</span>
          </NavLink>
          <NavLink to="/audit" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>
            <span className="nav-icon">📋</span> Audit Trail
          </NavLink>
          <NavLink to="/kb" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>
            <span className="nav-icon">📚</span> Knowledge Base
          </NavLink>
          <NavLink to="/demo" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>
            <span className="nav-icon">🎛️</span> Demo Control
          </NavLink>
        </nav>
        <div id="topbar-right">
          <span className="user-chip">
            {session.user.name} · {ROLE_LABELS[session.user.role] ?? session.user.role}
            <button onClick={() => logout()}>Sign out</button>
          </span>
        </div>
      </div>
      {paused && (
        <div className="banner" role="button" tabIndex={0} style={{ cursor: "pointer" }} onClick={refresh} onKeyDown={(e) => e.key === "Enter" && refresh()}>
          Paused - click to refresh
        </div>
      )}
      <Outlet />
    </>
  );
}

export default function App({ dataSource }: { dataSource?: DataSource }) {
  const ds = useMemo(() => dataSource ?? createDataSource(), [dataSource]);
  const client = useMemo(() => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } }), []);
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthProvider ds={ds}>
          <HashRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="queue" element={<Queue />} />
                <Route path="audit" element={<Audit />} />
                <Route path="kb" element={<KnowledgeBase />} />
                <Route path="demo" element={<DemoControl />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </HashRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
