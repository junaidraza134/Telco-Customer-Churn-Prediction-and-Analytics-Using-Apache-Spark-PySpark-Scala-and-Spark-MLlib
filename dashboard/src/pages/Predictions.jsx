import { useEffect, useState } from "react";
import { fetchPredictions } from "../api.js";

/* ── Risk badge ── */
function RiskBadge({ level }) {
  const map = {
    High:   { cls: "badge-high",   dot: "#f43f5e" },
    Medium: { cls: "badge-medium", dot: "#f59e0b" },
    Low:    { cls: "badge-low",    dot: "#10b981" },
  };
  const config = map[level];
  if (!config) return <span style={{ color: "var(--text-muted)" }}>—</span>;
  return (
    <span className={`badge ${config.cls}`}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: config.dot, display: "inline-block" }} />
      {level}
    </span>
  );
}

/* ── Probability bar ── */
function ProbBar({ value }) {
  const color = value >= 0.6 ? "#f43f5e" : value >= 0.3 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 99, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${value * 100}%`, background: color, borderRadius: 99, transition: "width 0.4s ease" }} />
      </div>
      <span className="mono" style={{ fontSize: "0.8rem", fontWeight: 700, color, minWidth: 48, textAlign: "right" }}>
        {value.toFixed(4)}
      </span>
    </div>
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
   PREDICTIONS PAGE
   ══════════════════════════════════════════════════════════ */
export default function Predictions() {
  const [customerID, setCustomerID] = useState("");
  const [risk,       setRisk]       = useState("");
  const [sort,       setSort]       = useState("desc");
  const [page,       setPage]       = useState(1);
  const [query,      setQuery]      = useState({ customerID: "", risk: "", sort: "desc", page: 1 });
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetchPredictions(query)
      .then((d) => { setData(d); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [query]);

  function search(e) {
    e.preventDefault();
    setPage(1);
    setQuery({ customerID, risk, sort, page: 1 });
  }

  function changePage(n) {
    setPage(n);
    setQuery({ ...query, page: n });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>

      {/* ── Header ── */}
      <div className="fade-in">
        <p className="section-eyebrow">Main Project Feature</p>
        <h2 style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: 4, letterSpacing: "-0.02em" }}>
          Customer <span className="gradient-text">Predictions</span>
        </h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: "0.9rem" }}>
          Search, sort, and filter churn scores stored in{" "}
          <code style={{ fontFamily: "var(--font-mono)", color: "#818cf8", fontSize: "0.85rem" }}>churn_db.predictions</code>
        </p>
      </div>

      {/* ── Search panel ── */}
      <div className="glass fade-in-2" style={{ padding: "24px" }}>
        <p style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: 16, color: "var(--text-secondary)" }}>
          🔍 Search &amp; filter predictions
        </p>
        <form onSubmit={search}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14, marginBottom: 16 }}>
            <Field label="Customer ID">
              <input
                className="form-input"
                value={customerID}
                onChange={(e) => setCustomerID(e.target.value)}
                placeholder="e.g. 7590-VHVEG"
              />
            </Field>
            <Field label="Risk level">
              <select className="form-select" value={risk} onChange={(e) => setRisk(e.target.value)}>
                <option value="">All risks</option>
                <option value="High">High (≥ 0.60)</option>
                <option value="Medium">Medium (0.30–0.60)</option>
                <option value="Low">Low (&lt; 0.30)</option>
              </select>
            </Field>
            <Field label="Sort by probability">
              <select className="form-select" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="desc">Highest first</option>
                <option value="asc">Lowest first</option>
              </select>
            </Field>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button type="submit" className="btn-primary" style={{ width: "100%" }}>
                Search
              </button>
            </div>
          </div>
        </form>

        {/* Summary chips */}
        {data && !loading && (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 12, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <span style={{
              padding: "4px 12px",
              borderRadius: 99,
              background: "rgba(99,102,241,0.12)",
              border: "1px solid rgba(99,102,241,0.3)",
              fontSize: "0.78rem",
              color: "#c7d2fe",
              fontWeight: 600,
            }}>
              {data.total.toLocaleString()} results
            </span>
            {risk && (
              <span style={{
                padding: "4px 12px",
                borderRadius: 99,
                background: "rgba(99,102,241,0.08)",
                border: "1px solid rgba(255,255,255,0.08)",
                fontSize: "0.78rem",
                color: "var(--text-secondary)",
              }}>
                Risk: {risk}
              </span>
            )}
          </div>
        )}
      </div>

      {error && (
        <div style={{ padding: "16px 20px", borderRadius: 14, border: "1px solid rgba(244,63,94,0.35)", background: "rgba(244,63,94,0.08)", color: "#fb7185", fontSize: "0.85rem" }}>
          ⚠ {error}
        </div>
      )}

      {/* ── Table ── */}
      <div className="glass fade-in-3" style={{ overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Customer ID</th>
                <th>Churn probability</th>
                <th>Risk</th>
                <th>Model used</th>
                <th>Scored at</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ padding: "48px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    Loading predictions from Spark data mart...
                  </td>
                </tr>
              ) : data?.rows.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: "48px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    No predictions match the current filter.
                  </td>
                </tr>
              ) : data?.rows.map((row) => (
                <tr key={row.customerID}>
                  <td>
                    <span className="mono" style={{ color: "#818cf8", fontSize: "0.82rem" }}>
                      {row.customerID}
                    </span>
                  </td>
                  <td style={{ minWidth: 200 }}>
                    <ProbBar value={Number(row.churn_probability)} />
                  </td>
                  <td>
                    <RiskBadge level={row.risk_level} />
                  </td>
                  <td>
                    <span style={{
                      padding: "3px 10px",
                      borderRadius: 99,
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      background: "rgba(99,102,241,0.12)",
                      border: "1px solid rgba(99,102,241,0.25)",
                      color: "#a5b4fc",
                    }}>
                      {row.model_used}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.78rem", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                    {row.scored_at ? new Date(row.scored_at).toLocaleString() : "—"}
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
              {data.total.toLocaleString()} scored customers · page {data.page} of {data.totalPages}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn-ghost"
                disabled={page <= 1}
                onClick={() => changePage(page - 1)}
                style={{ padding: "6px 14px", fontSize: "0.8rem" }}
              >
                ← Previous
              </button>
              <button
                className="btn-ghost"
                disabled={page >= data.totalPages}
                onClick={() => changePage(page + 1)}
                style={{ padding: "6px 14px", fontSize: "0.8rem" }}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Risk threshold note ── */}
      <div className="glass fade-in-4" style={{ padding: "20px 24px" }}>
        <p style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: 12 }}>⚙ Risk threshold definitions</p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {[
            { level: "High",   range: "probability ≥ 0.60", color: "#f43f5e", bg: "rgba(244,63,94,0.10)" },
            { level: "Medium", range: "0.30 ≤ probability < 0.60", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
            { level: "Low",    range: "probability < 0.30", color: "#10b981", bg: "rgba(16,185,129,0.10)" },
          ].map(({ level, range, color, bg }) => (
            <div key={level} style={{
              flex: "1 1 200px",
              background: bg,
              border: `1px solid ${color}44`,
              borderRadius: 12,
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: color, flexShrink: 0 }} />
              <div>
                <p style={{ fontWeight: 700, color, fontSize: "0.85rem" }}>{level} risk</p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>{range}</p>
              </div>
            </div>
          ))}
        </div>
        <p style={{ marginTop: 12, fontSize: "0.75rem", color: "var(--text-muted)" }}>
          These thresholds are illustrative business rules — not universally validated cutoffs. A high probability is a warning signal, not a guaranteed cancellation.
        </p>
      </div>
    </div>
  );
}
