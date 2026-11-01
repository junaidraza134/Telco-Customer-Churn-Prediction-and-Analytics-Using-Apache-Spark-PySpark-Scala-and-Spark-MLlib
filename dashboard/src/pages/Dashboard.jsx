import { useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchDashboard } from "../api.js";

/* ── Colours for risk donut ─── */
const riskColors = { High: "#f43f5e", Medium: "#f59e0b", Low: "#10b981" };
const contractColors = ["#6366f1", "#8b5cf6", "#a78bfa"];

/* ── Animate a number from 0 to target ─ */
function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(0);
  const raf = useRef(null);
  useEffect(() => {
    if (target == null) return;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(ease * target));
      if (t < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);
  return value;
}

/* ── Custom tooltip ─── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <p style={{ color: "var(--text-secondary)", marginBottom: 4, fontSize: "0.78rem" }}>{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color || "#818cf8", fontWeight: 600 }}>
          {typeof p.value === "number" && p.value < 2
            ? `${(p.value * 100).toFixed(1)}%`
            : p.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
}

/* ── Stat KPI card ─── */
function StatCard({ label, value, hint, color = "#818cf8", icon, delay = 0 }) {
  return (
    <div className="stat-card fade-in" style={{ animationDelay: `${delay}ms` }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
        <p style={{ fontSize: "0.78rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-secondary)" }}>
          {label}
        </p>
        <span style={{
          width: 36, height: 36, borderRadius: 10,
          background: `${color}22`,
          border: `1px solid ${color}44`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18,
        }}>{icon}</span>
      </div>
      <p style={{ fontSize: "2.2rem", fontWeight: 800, lineHeight: 1, color, letterSpacing: "-0.02em" }}>{value}</p>
      <p style={{ marginTop: 8, fontSize: "0.75rem", color: "var(--text-muted)" }}>{hint}</p>
    </div>
  );
}

/* ── Error box ─── */
function ErrorBox({ message }) {
  return (
    <div style={{
      borderRadius: 16,
      border: "1px solid rgba(244,63,94,0.35)",
      background: "rgba(244,63,94,0.08)",
      padding: "20px 24px",
      color: "#fda4af",
      fontSize: "0.9rem",
    }}>
      <strong style={{ display: "block", marginBottom: 6 }}>⚠ Could not load Spark analytical mart</strong>
      Could not load Spark analytical mart. Run the Spark pipeline and start the API.
      <br /><span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{message}</span>
    </div>
  );
}

/* ── Skeleton ─── */
function Skeleton({ h = 120 }) {
  return <div className="skeleton" style={{ height: h, borderRadius: 16 }} />;
}

/* ══════════════════════════════════════════════════════════
   DASHBOARD PAGE
   ══════════════════════════════════════════════════════════ */
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  /* Animated counts */
  const totalAnim    = useCountUp(data?.totalCustomers ?? 0);
  const highRiskAnim = useCountUp(data?.highRiskCount ?? 0);

  if (error) return <ErrorBox message={error} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>

      {/* ── Page header ── */}
      <div className="fade-in">
        <p className="section-eyebrow">Overview</p>
        <h2 style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: 4, letterSpacing: "-0.02em" }}>
          Churn <span className="gradient-text">Dashboard</span>
        </h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: "0.9rem" }}>
          Live data from <code style={{ fontFamily: "var(--font-mono)", color: "#818cf8", fontSize: "0.85rem" }}>customers.parquet</code> &amp;{" "}
          <code style={{ fontFamily: "var(--font-mono)", color: "#818cf8", fontSize: "0.85rem" }}>predictions.parquet</code>
        </p>
      </div>

      {/* ── KPI row ── */}
      {!data ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
          {[1, 2, 3, 4].map((k) => <Skeleton key={k} h={130} />)}
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
          <StatCard
            label="Total customers"
            value={totalAnim.toLocaleString()}
            hint="Verified IBM Telco dataset"
            color="#818cf8"
            icon="👥"
            delay={0}
          />
          <StatCard
            label="Overall churn rate"
            value={`${(data.churnRate * 100).toFixed(1)}%`}
            hint={`${data.churnedCount.toLocaleString()} customers left`}
            color="#f43f5e"
            icon="📉"
            delay={80}
          />
          <StatCard
            label="High-risk customers"
            value={highRiskAnim.toLocaleString()}
            hint="Predicted probability ≥ 0.60"
            color="#f59e0b"
            icon="⚠️"
            delay={160}
          />
          <StatCard
            label="Avg. predicted churn"
            value={`${(data.averageProbability * 100).toFixed(1)}%`}
            hint={data.modelUsed || "No model stored yet"}
            color="#10b981"
            icon="🎯"
            delay={240}
          />
        </div>
      )}

      {/* ── Charts row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

        {/* Contract churn bar chart */}
        <div className="glass fade-in-2" style={{ padding: "24px" }}>
          <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 4 }}>Churn rate by contract type</p>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 20 }}>
            Actual churn labels from Spark customers analytical mart
          </p>
          {!data ? <Skeleton h={260} /> : (
            <>
              <div style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.churnByContract} barSize={36}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis
                      dataKey="contract"
                      stroke="var(--text-muted)"
                      tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
                    />
                    <YAxis
                      tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                      stroke="var(--text-muted)"
                      tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="churnRate" radius={[6, 6, 0, 0]}>
                      {data.churnByContract.map((entry, i) => (
                        <Cell key={entry.contract} fill={contractColors[i % contractColors.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="divider" style={{ margin: "16px 0" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {data.churnByContract.map((row, i) => (
                  <div key={row.contract} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "0.82rem" }}>
                    <span style={{
                      width: 10, height: 10, borderRadius: 3, flexShrink: 0,
                      background: contractColors[i % contractColors.length],
                    }} />
                    <span style={{ color: "var(--text-secondary)", flex: 1 }}>{row.contract}</span>
                    <span style={{ fontWeight: 700, color: contractColors[i % contractColors.length] }}>
                      {(row.churnRate * 100).toFixed(1)}%
                    </span>
                    <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      {row.churned}/{row.customers}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Risk distribution donut */}
        <div className="glass fade-in-3" style={{ padding: "24px" }}>
          <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 4 }}>Predicted risk distribution</p>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 20 }}>
            From <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem", color: "#818cf8" }}>predictions.parquet</code>
          </p>
          {!data ? <Skeleton h={260} /> : (
            <>
              <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: "High",   value: data.riskCounts.High },
                        { name: "Medium", value: data.riskCounts.Medium },
                        { name: "Low",    value: data.riskCounts.Low },
                      ]}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={88}
                      paddingAngle={3}
                    >
                      {["High", "Medium", "Low"].map((k) => (
                        <Cell key={k} fill={riskColors[k]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend
                      formatter={(v) => <span style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{v}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="divider" style={{ margin: "16px 0" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {["High", "Medium", "Low"].map((level) => {
                  const count = data.riskCounts[level];
                  const total = data.riskCounts.High + data.riskCounts.Medium + data.riskCounts.Low;
                  const pct = total ? count / total : 0;
                  return (
                    <div key={level}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: 4 }}>
                        <span style={{ color: "var(--text-secondary)" }}>{level} risk</span>
                        <span style={{ fontWeight: 700, color: riskColors[level] }}>
                          {count.toLocaleString()} ({(pct * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${pct * 100}%`,
                            background: riskColors[level],
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Model info strip ── */}
      {data && (
        <div className="glass fade-in-4" style={{
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}>
          <span className="live-dot" />
          <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>Active model:</span>
          <span style={{
            padding: "3px 12px",
            borderRadius: 99,
            background: "rgba(99,102,241,0.18)",
            border: "1px solid rgba(99,102,241,0.35)",
            color: "#c7d2fe",
            fontWeight: 700,
            fontSize: "0.82rem",
            fontFamily: "var(--font-mono)",
          }}>{data.modelUsed || "—"}</span>
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            Last scored:{" "}
            {data.scoredAt
              ? new Date(data.scoredAt).toLocaleString()
              : "N/A"}
          </span>
        </div>
      )}
    </div>
  );
}
