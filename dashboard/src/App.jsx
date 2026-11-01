import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import Explore from "./pages/Explore.jsx";
import Performance from "./pages/Performance.jsx";
import Predictions from "./pages/Predictions.jsx";

const links = [
  { to: "/",            label: "Dashboard",           icon: "⬡" },
  { to: "/explore",     label: "Explore Data",        icon: "⊞" },
  { to: "/performance", label: "Model Performance",   icon: "◈" },
  { to: "/predictions", label: "Predictions",         icon: "◎" },
];

export default function App() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* ── Header ─────────────────────────────────────────── */}
      <header style={{
        borderBottom: "1px solid rgba(255,255,255,0.07)",
        background: "rgba(4,5,13,0.8)",
        backdropFilter: "blur(20px)",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}>
        <div style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: "0 24px",
          height: 64,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
        }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            <div style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              boxShadow: "0 4px 16px rgba(99,102,241,0.5)",
            }}>⚡</div>
            <div>
              <div style={{ fontSize: "0.68rem", fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#818cf8" }}>
                Apache Spark · PySpark · Scala
              </div>
              <div style={{ fontSize: "1rem", fontWeight: 700, lineHeight: 1.2, color: "#f0f2ff" }}>
                Telco Churn Analytics
              </div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ display: "flex", gap: 4, overflowX: "auto" }}>
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                style={{ textDecoration: "none" }}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "nav-active" : ""}`
                }
              >
                {({ isActive }) => (
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 14px",
                    borderRadius: 10,
                    fontSize: "0.82rem",
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? "#c7d2fe" : "#8b91b8",
                    whiteSpace: "nowrap",
                  }}>
                    <span style={{ fontSize: "0.9rem" }}>{link.icon}</span>
                    {link.label}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Live indicator */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: "0.75rem",
            color: "#34d399",
            fontWeight: 600,
            flexShrink: 0,
          }}>
            <span className="live-dot" />
            Spark Engine Active · Parquet Ready
          </div>
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────── */}
      <main style={{ flex: 1, maxWidth: 1280, width: "100%", margin: "0 auto", padding: "32px 24px" }}>
        <Routes>
          <Route path="/"            element={<Dashboard />} />
          <Route path="/explore"     element={<Explore />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/predictions" element={<Predictions />} />
        </Routes>
      </main>

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer style={{
        borderTop: "1px solid rgba(255,255,255,0.05)",
        padding: "20px 24px",
        textAlign: "center",
        fontSize: "0.75rem",
        color: "var(--text-muted)",
      }}>
        IBM Telco Churn dataset · 7,043 customers · Apache Spark MLlib &amp; Parquet Engine
      </footer>
    </div>
  );
}
