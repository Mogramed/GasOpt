import { createContext, useContext, useEffect, useState } from "react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  ChartNoAxesCombined,
  Database,
  FlaskConical,
  GitBranch,
  Grid2X2,
  Layers,
  Sigma,
  ShieldCheck,
  ListFilter,
  ChevronRight,
  BookOpen,
} from "lucide-react";
import { useApi, type Meta, type Tx, type Result, type Profile } from "./api";
import { ErrorState, Loading } from "./components";
import { Overview, DataPage, WorkloadPage, Methodology } from "./pages/Explore";
import {
  Optimizer,
  RiskPage,
  ScenarioPage,
  ResultsPage,
} from "./pages/Laboratory";
import { ModelPage, SolverPage } from "./pages/Education";
type Workspace = {
  meta: Meta;
  workload: Tx[];
  profile: Profile[];
  mean: Result;
  current: Result;
  setCurrent: (r: Result) => void;
  viewedTest: boolean;
  markTest: () => void;
};
const Context = createContext<Workspace | null>(null);
export function useWorkspace() {
  const c = useContext(Context);
  if (!c) throw new Error("Workspace unavailable");
  return c;
}
const links = [
  ["overview", "Overview", Grid2X2],
  ["data", "Data explorer", Database],
  ["workload", "Treasury workload", Layers],
  ["model", "Mathematical model", Sigma],
  ["optimizer", "Optimization lab", FlaskConical],
  ["scenarios", "Scenario explorer", Activity],
  ["risk", "Risk & CVaR", ShieldCheck],
  ["results", "TEST results", ChartNoAxesCombined],
  ["solver", "Solver explorer", GitBranch],
  ["methodology", "Methodology", BookOpen],
] as const;
export default function App() {
  const meta = useApi<Meta>("study/meta"),
    workload = useApi<Tx[]>("workload"),
    profile = useApi<Profile[]>("data/slot-profile"),
    mean = useApi<Result>("study/archive/mean_price");
  const [selected, setCurrent] = useState<Result | null>(null),
    [viewedTest, setViewedTest] = useState(false);
  const location = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  const error = meta.error || workload.error || profile.error || mean.error;
  const ready = meta.data && workload.data && profile.data && mean.data;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <NavLink to="/overview" className="brand">
          <span className="brand-mark">
            <Sigma size={25} />
          </span>
          GasOps<span className="brand-dot">.</span>
        </NavLink>
        <div className="workspace-label">
          RESEARCH WORKSPACE <span>01</span>
        </div>
        <nav>
          {links.map(([path, name, Icon], i) => (
            <NavLink
              key={path}
              to={"/" + path}
              aria-label={name}
              title={name}
              className={({ isActive }) =>
                isActive ? "nav-item active" : "nav-item"
              }
            >
              <Icon size={17} />
              <span>{name}</span>
              {path === "optimizer" && (
                <span className="nav-shortcut">LAB</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div>
            <span className="status-dot" /> LOCAL STUDY
          </div>
          <p>
            Ethereum Mainnet
            <br />
            MSc Finance & Big Data
          </p>
          <div className="sidebar-id">
            {meta.data?.dataset_id.slice(0, 8) ?? "CONNECTING"}
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span>GasOps</span>
            <ChevronRight size={13} />
            {links.find((x) => location.pathname === "/" + x[0])?.[1] ??
              "Workspace"}
          </div>
          <div className="topbar-right">
            <span className="status-dot" /> Offline-ready{" "}
            <span className="topbar-divider" /> <span>ETH</span>
            <span className="network">MAINNET DATA</span>
          </div>
        </header>
        <main id="main">
          {error ? (
            <ErrorState
              error={error as Error}
              retry={() => window.location.reload()}
            />
          ) : !ready ? (
            <Loading />
          ) : (
            <Context.Provider
              value={{
                meta: meta.data!,
                workload: workload.data!,
                profile: profile.data!,
                mean: mean.data!,
                current: selected ?? mean.data!,
                setCurrent,
                viewedTest,
                markTest: () => setViewedTest(true),
              }}
            >
              <AnimatePresence mode="wait">
                <motion.div
                  key={location.pathname}
                  initial={{ opacity: 0, y: 7 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.16 }}
                >
                  <Routes location={location}>
                    <Route path="/overview" element={<Overview />} />
                    <Route path="/data" element={<DataPage />} />
                    <Route path="/workload" element={<WorkloadPage />} />
                    <Route path="/model" element={<ModelPage />} />
                    <Route path="/optimizer" element={<Optimizer />} />
                    <Route path="/scenarios" element={<ScenarioPage />} />
                    <Route path="/risk" element={<RiskPage />} />
                    <Route path="/results" element={<ResultsPage />} />
                    <Route path="/solver" element={<SolverPage />} />
                    <Route path="/methodology" element={<Methodology />} />
                    <Route
                      path="*"
                      element={<Navigate to="/overview" replace />}
                    />
                  </Routes>
                </motion.div>
              </AnimatePresence>
            </Context.Provider>
          )}
          <footer className="footer">
            <span>GasOps · Empirical optimization laboratory</span>
            <span>
              Historical observations. Explicit assumptions. Reproducible
              decisions.
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
