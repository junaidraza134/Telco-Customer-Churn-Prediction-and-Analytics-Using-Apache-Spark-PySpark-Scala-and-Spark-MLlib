import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchModel } from "../api.js";

function cleanName(n) {
  return n.replace(/^num__/, "").replace(/^cat__/, "").replace(/_/g, " ");
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <p style={{ color: "var(--text-secondary)", fontSize: "0.78rem", marginBottom: 4 }}>{label}</p>
      <p style={{ color: "#818cf8", fontWeight: 700 }}>{payload[0].value.toFixed(4)}</p>
    </div>
  );
}

/* ── Metric pill ── */
function MetricPill({ label, value, highlight }) {
  return (
    <div style={{
      background: highlight ? "rgba(99,102,241,0.12)" : "rgba(255,255,255,0.03)",
      border: `1px solid ${highlight ? "rgba(99,102,241,0.35)" : "rgba(255,255,255,0.06)"}`,
      borderRadius: 12,
      padding: "12px 16px",
      textAlign: "center",
    }}>
      <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
        {label}
      </p>
      <p style={{
        fontSize: "1.3rem",
        fontWeight: 800,
        fontFamily: "var(--font-mono)",
        color: highlight ? "#818cf8" : "var(--text-primary)",
        letterSpacing: "-0.02em",
      }}>
        {typeof value === "number" ? value.toFixed(4) : value}
      </p>
    </div>
  );
}

/* ── Confusion matrix cell ── */
function CMCell({ label, value, cls, labelColor }) {
  return (
    <div className={`cm-cell ${cls}`} style={{ transition: "transform 0.2s" }}>
      <p style={{ fontSize: "2rem", fontWeight: 800, fontFamily: "var(--font-mono)" }}>{value}</p>
      <p style={{ fontSize: "0.72rem", color: labelColor, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: 4 }}>
        {label}
      </p>
    </div>
  );
}

/* ── Model comparison row ── */
function ModelRow({ model, best }) {
  const isBest = model.name === best;
  return (
    <tr style={{ background: isBest ? "rgba(99,102,241,0.07)" : "transparent" }}>
      <td style={{ padding: "14px 16px", fontWeight: 700 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {model.name}
          {isBest && (
            <span style={{
              padding: "2px 8px",
              borderRadius: 99,
              fontSize: "0.68rem",
              fontWeight: 700,
              background: "rgba(99,102,241,0.25)",
              border: "1px solid rgba(99,102,241,0.5)",
              color: "#c7d2fe",
            }}>SELECTED</span>
          )}
        </div>
      </td>
      {["accuracy","precision","recall","f1","roc_auc"].map((k) => (
        <td key={k} style={{
          padding: "14px 16px",
          fontFamily: "var(--font-mono)",
          fontSize: "0.88rem",
          fontWeight: k === "roc_auc" ? 700 : 400,
          color: k === "roc_auc" ? (isBest ? "#818cf8" : "var(--text-primary)") : "var(--text-primary)",
        }}>
          {model[k].toFixed(4)}
        </td>
      ))}
    </tr>
  );
}

/* ══════════════════════════════════════════════════════════
   PERFORMANCE PAGE
   ══════════════════════════════════════════════════════════ */
export default function Performance() {
  const [data,    setData]    = useState(null);
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchModel()
      .then((d) => { setData(d); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, []);

  if (error) return (
    <div style={{ padding: "20px 24px", borderRadius: 16, border: "1px solid rgba(244,63,94,0.35)", background: "rgba(244,63,94,0.08)", color: "#fda4af" }}>
      ⚠ Could not load model data — make sure you have run <code style={{ fontFamily: "var(--font-mono)" }}>python spark-pipeline/spark_train.py</code> and the API is started.
      <br /><span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{error}</span>
    </div>
  );

  const chartData = data?.feature_importance_top10.map(([name, value]) => ({
    name: cleanName(name),
    value,
  })) ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>

      {/* ── Header ── */}
      <div className="fade-in">
        <p className="section-eyebrow">ML Evaluation</p>
        <h2 style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: 4, letterSpacing: "-0.02em" }}>
          Model <span className="gradient-text">Performance</span>
        </h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: "0.9rem" }}>
          Metrics computed on the held-out 20% test set ({data?.test_size ? data.test_size.toLocaleString() : "1,247"} customers) via Stratified Hold-out + Spark MLlib Pipeline. Selected model:{" "}
          <strong style={{ color: "#c7d2fe" }}>{data?.selected_model ?? "—"}</strong>
        </p>
      </div>

      {/* ── Comparison table ── */}
      <div className="glass fade-in-2" style={{ overflow: "hidden" }}>
        <div style={{ padding: "20px 24px 0" }}>
          <p style={{ fontWeight: 700, fontSize: "0.95rem" }}>All Models Benchmark (Gradient Boosted &amp; Classical Ensembles)</p>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 4 }}>
            Precision, Recall, F1 computed for the churn class (1). ROC-AUC uses predicted probabilities.
          </p>
        </div>
        <div style={{ overflowX: "auto", marginTop: 16 }}>
          <table className="data-table">
            <thead>
              <tr>
                {["Model","Accuracy","Precision","Recall","F1-score","ROC-AUC"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? <tr><td colSpan={6} style={{ padding: "40px 0", textAlign: "center", color: "var(--text-muted)" }}>Loading metrics...</td></tr>
                : data?.models.map((m) => (
                  <ModelRow key={m.name} model={m} best={data.selected_model} />
                ))
              }
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Confusion matrices ── */}
      {data && (
        <div className="fade-in-3" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 20 }}>
          {data.models.map((model) => {
            const [[tn, fp], [fn, tp]] = model.confusion_matrix;
            return (
              <div key={model.name} className="glass" style={{ padding: "24px" }}>
                <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 4 }}>
                  {model.name}
                </p>
                <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 16 }}>
                  Confusion matrix — test set
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
                  <CMCell label="True Negative"  value={tn} cls="cm-tn" labelColor="#34d399" />
                  <CMCell label="False Positive" value={fp} cls="cm-fp" labelColor="#f87171" />
                  <CMCell label="False Negative" value={fn} cls="cm-fn" labelColor="#fbbf24" />
                  <CMCell label="True Positive"  value={tp} cls="cm-tp" labelColor="#818cf8" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
                  <MetricPill label="Accuracy"  value={model.accuracy}  />
                  <MetricPill label="F1-score"  value={model.f1}        />
                  <MetricPill label="ROC-AUC"   value={model.roc_auc}   highlight={model.name === data.selected_model} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Feature importance ── */}
      {data && (
        <div className="fade-in-4" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Interactive chart */}
          <div className="glass" style={{ padding: "24px" }}>
            <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 4 }}>
              Random Forest — top 10 features
            </p>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 20 }}>
              Predictive contribution (not causation)
            </p>
            <div style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[...chartData].reverse()}
                  layout="vertical"
                  margin={{ left: 8, right: 16 }}
                  barSize={18}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                  <XAxis
                    type="number"
                    stroke="var(--text-muted)"
                    tick={{ fontSize: 10, fill: "var(--text-secondary)" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={170}
                    stroke="var(--text-muted)"
                    tick={{ fontSize: 10, fill: "var(--text-secondary)" }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="value"
                    radius={[0, 6, 6, 0]}
                    fill="url(#featureGrad)"
                  />
                  <defs>
                    <linearGradient id="featureGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%"   stopColor="#6366f1" />
                      <stop offset="100%" stopColor="#a78bfa" />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Matplotlib saved image */}
          <div className="glass" style={{ padding: "24px" }}>
            <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 4 }}>
              Saved matplotlib chart
            </p>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 16 }}>
              Generated by <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#818cf8' }}>Spark MLlib Pipeline</code> and served via API
            </p>
            <div style={{
              borderRadius: 12,
              overflow: "hidden",
              border: "1px solid rgba(255,255,255,0.08)",
              background: "#fff",
            }}>
              <img
                src="/api/feature-importance.png"
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = "/feature_importance.png";
                }}
                alt="Random Forest feature importance chart"
                style={{ width: "100%", display: "block" }}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Metric explainer ── */}
      <div className="glass fade-in" style={{ padding: "24px" }}>
        <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 16 }}>
          📖 How to read these metrics
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
          {[
            { term: "True Positive (TP)",  def: "Churned customers the model correctly flagged.",               color: "#818cf8" },
            { term: "True Negative (TN)",  def: "Retained customers correctly left unflagged.",                  color: "#34d399" },
            { term: "False Positive (FP)", def: "Retained customers wrongly flagged as churn (wasted offer).",   color: "#f87171" },
            { term: "False Negative (FN)", def: "Churned customers the model missed (lost revenue).",            color: "#fbbf24" },
            { term: "Precision",           def: "Of all predicted churners, what fraction actually churned.",    color: "#a78bfa" },
            { term: "Recall",              def: "Of all real churners, what fraction the model found.",          color: "#60a5fa" },
            { term: "F1-score",            def: "Harmonic mean of precision and recall. Balances both.",        color: "#34d399" },
            { term: "ROC-AUC",             def: "Ranking quality across all thresholds. 0.5 = chance, 1 = perfect.", color: "#f59e0b" },
          ].map(({ term, def, color }) => (
            <div key={term} style={{
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 12,
              padding: "12px 14px",
            }}>
              <p style={{ fontSize: "0.78rem", fontWeight: 700, color, marginBottom: 4 }}>{term}</p>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>{def}</p>
            </div>
          ))}
        </div>
        <div style={{
          marginTop: 16,
          padding: "12px 16px",
          borderRadius: 12,
          background: "rgba(245,158,11,0.08)",
          border: "1px solid rgba(245,158,11,0.25)",
          fontSize: "0.82rem",
          color: "#fbbf24",
        }}>
          ⚠ <strong>Why accuracy alone misleads:</strong> ~73.5% of customers did not churn, so a model that always predicts "retained" would look accurate but catch zero churners.
        </div>
      </div>
    </div>
  );
}
