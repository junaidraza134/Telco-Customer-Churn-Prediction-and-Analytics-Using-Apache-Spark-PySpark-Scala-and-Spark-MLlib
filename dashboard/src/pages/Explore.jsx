import { useEffect, useState } from "react";
import { fetchCustomers } from "../api.js";

const emptyFilters = { contract: "", churn: "", tenureMin: "", tenureMax: "" };

/* ── Skeleton ── */
function Skeleton({ h = 80 }) {
  return <div className="skeleton" style={{ height: h, borderRadius: 14, marginBottom: 8 }} />;
}

/* ── Stat summary card ── */
function CompareCard({ title, stats, accent }) {
  if (!stats) return (
    <div className="glass" style={{ padding: "20px 24px" }}>
      <p style={{ fontWeight: 700, fontSize: "0.9rem", color: accent }}>{title}</p>
      <p style={{ marginTop: 8, fontSize: "0.82rem", color: "var(--text-muted)" }}>
        No customers in this group for the current filter.
      </p>
    </div>
  );
  const metrics = [
    { label: "Count",         value: stats.count.toLocaleString() },
    { label: "Avg tenure",    value: `${stats.avgTenure.toFixed(1)} mo` },
    { label: "Avg monthly",   value: `$${stats.avgMonthly.toFixed(2)}` },
    { label: "Avg total",     value: `$${stats.avgTotal.toFixed(0)}` },
  ];
  return (
    <div className="glass" style={{ padding: "20px 24px" }}>
      <p style={{ fontWeight: 700, fontSize: "0.9rem", color: accent, marginBottom: 14 }}>{title}</p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {metrics.map(({ label, value }) => (
          <div key={label} style={{
            background: "rgba(255,255,255,0.03)",
            borderRadius: 10,
            padding: "10px 12px",
            border: "1px solid rgba(255,255,255,0.05)",
          }}>
            <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
              {label}
            </p>
            <p style={{ fontSize: "1.05rem", fontWeight: 700, color: accent }}>{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Risk badge ── */
function RiskBadge({ level }) {
  if (!level) return <span style={{ color: "var(--text-muted)" }}>—</span>;
  const cls = { High: "badge-high", Medium: "badge-medium", Low: "badge-low" };
  const dot = { High: "#f43f5e", Medium: "#f59e0b", Low: "#10b981" };
  return (
    <span className={`badge ${cls[level] || ""}`}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: dot[level], display: "inline-block" }} />
      {level}
    </span>
  );
}

/* ── Form field ── */
function Field({ label, children }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: "0.82rem" }}>
      <span style={{ fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.07em", fontSize: "0.7rem" }}>
        {label}
      </span>
      {children}
    </label>
  );
}

/* ══════════════════════════════════════════════════════════
   EXPLORE PAGE
   ══════════════════════════════════════════════════════════ */
export default function Explore() {
  const [filters, setFilters]   = useState(emptyFilters);
  const [applied, setApplied]   = useState({ ...emptyFilters, page: 1 });
  const [data,    setData]      = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error,   setError]     = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetchCustomers(applied)
      .then((d) => { setData(d); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [applied]);

  function applyFilters(e) {
    e.preventDefault();
    setApplied({ ...filters, page: 1 });
  }

  function resetFilters() {
    setFilters(emptyFilters);
    setApplied({ ...emptyFilters, page: 1 });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>

      {/* ── Header ── */}
      <div className="fade-in">
        <p className="section-eyebrow">Customer Analysis</p>
        <h2 style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: 4, letterSpacing: "-0.02em" }}>
          Explore <span className="gradient-text">Data</span>
        </h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: "0.9rem" }}>
          Browse and filter the 7,043 customer records stored in the Spark Parquet mart
        </p>
      </div>

      {/* ── Filter panel ── */}
      <div className="glass fade-in-2" style={{ padding: "24px" }}>
        <p style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: 16, color: "var(--text-secondary)" }}>
          🔍 Filter customers
        </p>
        <form onSubmit={applyFilters}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14, marginBottom: 16 }}>
            <Field label="Contract type">
              <select
                className="form-select"
                value={filters.contract}
                onChange={(e) => setFilters({ ...filters, contract: e.target.value })}
              >
                <option value="">All types</option>
                <option value="Month-to-month">Month-to-month</option>
                <option value="One year">One year</option>
                <option value="Two year">Two year</option>
              </select>
            </Field>
            <Field label="Churn status">
              <select
                className="form-select"
                value={filters.churn}
                onChange={(e) => setFilters({ ...filters, churn: e.target.value })}
              >
                <option value="">All</option>
                <option value="Yes">Churned (Yes)</option>
                <option value="No">Retained (No)</option>
              </select>
            </Field>
            <Field label="Min tenure (mo)">
              <input
                type="number"
                min="0"
                className="form-input"
                placeholder="0"
                value={filters.tenureMin}
                onChange={(e) => setFilters({ ...filters, tenureMin: e.target.value })}
              />
            </Field>
            <Field label="Max tenure (mo)">
              <input
                type="number"
                min="0"
                className="form-input"
                placeholder="72"
                value={filters.tenureMax}
                onChange={(e) => setFilters({ ...filters, tenureMax: e.target.value })}
              />
            </Field>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button type="submit" className="btn-primary">Apply filters</button>
            <button type="button" className="btn-ghost" onClick={resetFilters}>Reset</button>
          </div>
        </form>
      </div>

      {error && (
        <div style={{ padding: "16px 20px", borderRadius: 14, border: "1px solid rgba(244,63,94,0.35)", background: "rgba(244,63,94,0.08)", color: "#fb7185", fontSize: "0.85rem" }}>
          ⚠ {error}
        </div>
      )}

      {/* ── Compare cards ── */}
      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Skeleton h={150} /><Skeleton h={150} />
        </div>
      ) : data && (
        <div className="fade-in" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <CompareCard title="📉 Churned customers"  stats={data.comparison.churned}  accent="#f87171" />
          <CompareCard title="✅ Retained customers" stats={data.comparison.retained} accent="#34d399" />
        </div>
      )}

      {/* ── Customer table ── */}
      <div className="glass fade-in-3" style={{ overflow: "hidden" }}>
        <div style={{ padding: "20px 24px 0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <p style={{ fontWeight: 700, fontSize: "0.95rem" }}>Customer records</p>
          {data && !loading && (
            <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
              {data.total.toLocaleString()} results · page {data.page}/{data.totalPages}
            </span>
          )}
        </div>
        <div style={{ overflowX: "auto", marginTop: 16 }}>
          <table className="data-table">
            <thead>
              <tr>
                {["Customer ID","Contract","Tenure","Internet","Monthly","Churn","Risk","Probability"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} style={{ padding: "48px 0", textAlign: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>⟳</span>
                    Loading from Spark data mart...
                  </div>
                </td></tr>
              ) : data?.rows.map((row) => (
                <tr key={row.customerID}>
                  <td>
                    <span className="mono" style={{ color: "#818cf8", fontSize: "0.8rem" }}>
                      {row.customerID}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.82rem" }}>{row.Contract}</td>
                  <td style={{ fontSize: "0.82rem", textAlign: "center" }}>{row.tenure}</td>
                  <td style={{ fontSize: "0.82rem" }}>{row.InternetService}</td>
                  <td style={{ fontSize: "0.82rem" }}>${Number(row.MonthlyCharges).toFixed(2)}</td>
                  <td>
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: 99,
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      background: row.Churn === "Yes" ? "rgba(244,63,94,0.18)" : "rgba(16,185,129,0.18)",
                      color: row.Churn === "Yes" ? "#fb7185" : "#34d399",
                      border: `1px solid ${row.Churn === "Yes" ? "rgba(244,63,94,0.3)" : "rgba(16,185,129,0.3)"}`,
                    }}>
                      {row.Churn}
                    </span>
                  </td>
                  <td><RiskBadge level={row.risk_level} /></td>
                  <td>
                    {row.churn_probability == null
                      ? <span style={{ color: "var(--text-muted)" }}>—</span>
                      : <span className="mono" style={{
                          fontSize: "0.82rem",
                          color: row.churn_probability >= 0.6 ? "#f87171"
                               : row.churn_probability >= 0.3 ? "#fbbf24"
                               : "#34d399",
                          fontWeight: 600,
                        }}>
                          {row.churn_probability.toFixed(4)}
                        </span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && !loading && (
          <div style={{
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: "1px solid rgba(255,255,255,0.05)",
          }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              {data.total.toLocaleString()} customers · page {data.page} of {data.totalPages}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn-ghost"
                disabled={data.page <= 1}
                onClick={() => setApplied({ ...applied, page: data.page - 1 })}
                style={{ padding: "6px 14px", fontSize: "0.8rem" }}
              >
                ← Previous
              </button>
              <button
                className="btn-ghost"
                disabled={data.page >= data.totalPages}
                onClick={() => setApplied({ ...applied, page: data.page + 1 })}
                style={{ padding: "6px 14px", fontSize: "0.8rem" }}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
