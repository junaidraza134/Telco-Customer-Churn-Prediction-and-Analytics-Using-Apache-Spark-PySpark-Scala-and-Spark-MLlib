import cors from "cors";
import express from "express";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read .env if present
const ENV_PATH = path.resolve(__dirname, ".env");
if (fs.existsSync(ENV_PATH)) {
  const envContent = fs.readFileSync(ENV_PATH, "utf8");
  for (const line of envContent.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const [key, ...vals] = trimmed.split("=");
    if (key && vals.length > 0) {
      process.env[key.trim()] = vals.join("=").trim();
    }
  }
}

const PORT = Number(process.env.PORT || 4000);
const DATA_DIR = path.resolve(__dirname, process.env.DATA_DIR || "../data/processed");
const REPORTS_DIR = path.resolve(__dirname, process.env.REPORTS_DIR || "../reports");

const PATHS = {
  dashboardSummary: path.join(DATA_DIR, "analytics", "dashboard_summary.json"),
  customers: path.join(DATA_DIR, "api_exports", "customers.json"),
  predictions: path.join(DATA_DIR, "api_exports", "predictions.json"),
  evaluationSummary: path.join(REPORTS_DIR, "evaluation_summary.json"),
  clusteringSummary: path.join(REPORTS_DIR, "clustering_summary.json"),
  featurePlot: path.join(REPORTS_DIR, "feature_importance.png"),
};

// In-memory data store
let store = {
  dashboardSummary: null,
  customers: null,
  predictions: null,
  predictionMap: new Map(),
  evaluationSummary: null,
  clusteringSummary: null,
};

function loadJsonSafe(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, "utf8");
      return JSON.parse(raw);
    }
  } catch (err) {
    console.error(`[DataMart] Error loading ${filePath}:`, err.message);
  }
  return null;
}

function reloadAll() {
  store.dashboardSummary = loadJsonSafe(PATHS.dashboardSummary);
  store.customers = loadJsonSafe(PATHS.customers);
  store.predictions = loadJsonSafe(PATHS.predictions);
  store.evaluationSummary = loadJsonSafe(PATHS.evaluationSummary);
  store.clusteringSummary = loadJsonSafe(PATHS.clusteringSummary);

  if (Array.isArray(store.predictions)) {
    store.predictionMap.clear();
    for (const p of store.predictions) {
      store.predictionMap.set(p.customerID, p);
    }
  }

  const loadedCount = [
    store.dashboardSummary,
    store.customers,
    store.predictions,
    store.evaluationSummary,
  ].filter(Boolean).length;
  console.log(`[DataMart] Loaded ${loadedCount}/4 primary analytical marts into memory.`);
}

// Watch files for hot reloading (500ms debounce)
const debounceTimers = new Map();
function setupWatcher(key, filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  try {
    fs.watch(dir, (_event, filename) => {
      if (filename && path.basename(filePath) === filename) {
        if (debounceTimers.has(key)) {
          clearTimeout(debounceTimers.get(key));
        }
        const timer = setTimeout(() => {
          console.log(`[DataMart] Hot reloading ${filename}...`);
          if (key === "predictions") {
            store.predictions = loadJsonSafe(filePath);
            if (Array.isArray(store.predictions)) {
              store.predictionMap.clear();
              for (const p of store.predictions) {
                store.predictionMap.set(p.customerID, p);
              }
            }
          } else {
            store[key] = loadJsonSafe(filePath);
          }
        }, 500);
        debounceTimers.set(key, timer);
      }
    });
  } catch (err) {
    console.warn(`[DataMart] Could not attach file watcher to ${dir}:`, err.message);
  }
}

// Initial load & watcher setup
reloadAll();
setupWatcher("dashboardSummary", PATHS.dashboardSummary);
setupWatcher("customers", PATHS.customers);
setupWatcher("predictions", PATHS.predictions);
setupWatcher("evaluationSummary", PATHS.evaluationSummary);
setupWatcher("clusteringSummary", PATHS.clusteringSummary);

const app = express();
app.use(cors());
app.use(express.json());

// Endpoints
app.get("/api/health", (_req, res) => {
  const ready =
    !!store.dashboardSummary &&
    !!store.customers &&
    !!store.predictions &&
    !!store.evaluationSummary;

  res.status(ready ? 200 : 503).json({
    ok: ready,
    spark: "ready",
    architecture: "Apache Spark / Parquet Analytical Mart",
    memoryStatus: {
      dashboardSummary: !!store.dashboardSummary,
      customers: Array.isArray(store.customers) ? store.customers.length : 0,
      predictions: Array.isArray(store.predictions) ? store.predictions.length : 0,
      evaluationSummary: !!store.evaluationSummary,
      clusteringSummary: !!store.clusteringSummary,
    },
  });
});

app.get("/api/dashboard", (_req, res) => {
  if (!store.dashboardSummary) {
    return res.status(503).json({
      error: "Could not load Spark analytical mart. Run the Spark pipeline and start the API.",
    });
  }
  res.json(store.dashboardSummary);
});

app.get("/api/customers", (req, res) => {
  if (!store.customers) {
    return res.status(503).json({
      error: "Customers mart is missing. Run spark_ingest.py first.",
    });
  }

  const contract = String(req.query.contract || "").trim();
  const churn = String(req.query.churn || "").trim();
  const tenureMin = req.query.tenureMin === undefined || req.query.tenureMin === "" ? null : Number(req.query.tenureMin);
  const tenureMax = req.query.tenureMax === undefined || req.query.tenureMax === "" ? null : Number(req.query.tenureMax);
  const page = Math.max(1, Number(req.query.page || 1));
  const pageSize = Math.min(50, Math.max(5, Number(req.query.pageSize || 12)));

  // Filter in memory
  let filtered = store.customers;
  if (contract) {
    filtered = filtered.filter((c) => c.Contract === contract);
  }
  if (churn === "Yes" || churn === "No") {
    filtered = filtered.filter((c) => c.Churn === churn);
  }
  if (Number.isFinite(tenureMin)) {
    filtered = filtered.filter((c) => c.tenure >= tenureMin);
  }
  if (Number.isFinite(tenureMax)) {
    filtered = filtered.filter((c) => c.tenure <= tenureMax);
  }

  // Aggregate comparison metrics (churned vs retained)
  const stats = {
    churned: { count: 0, sumTenure: 0, sumMonthly: 0, sumTotal: 0 },
    retained: { count: 0, sumTenure: 0, sumMonthly: 0, sumTotal: 0 },
  };

  for (const c of filtered) {
    const bucket = c.Churn === "Yes" ? stats.churned : stats.retained;
    bucket.count += 1;
    bucket.sumTenure += Number(c.tenure || 0);
    bucket.sumMonthly += Number(c.MonthlyCharges || 0);
    bucket.sumTotal += Number(c.TotalCharges || 0);
  }

  const comparison = {
    churned: stats.churned.count
      ? {
          count: stats.churned.count,
          avgTenure: stats.churned.sumTenure / stats.churned.count,
          avgMonthly: stats.churned.sumMonthly / stats.churned.count,
          avgTotal: stats.churned.sumTotal / stats.churned.count,
        }
      : null,
    retained: stats.retained.count
      ? {
          count: stats.retained.count,
          avgTenure: stats.retained.sumTenure / stats.retained.count,
          avgMonthly: stats.retained.sumMonthly / stats.retained.count,
          avgTotal: stats.retained.sumTotal / stats.retained.count,
        }
      : null,
  };

  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageSlice = filtered.slice((page - 1) * pageSize, page * pageSize);

  // Attach predictions if available
  const rows = pageSlice.map((row) => {
    const pred = store.predictionMap.get(row.customerID);
    return {
      customerID: row.customerID,
      gender: row.gender,
      SeniorCitizen: row.SeniorCitizen,
      Partner: row.Partner,
      Dependents: row.Dependents,
      tenure: row.tenure,
      Contract: row.Contract,
      InternetService: row.InternetService,
      PaymentMethod: row.PaymentMethod,
      MonthlyCharges: row.MonthlyCharges,
      TotalCharges: row.TotalCharges,
      Churn: row.Churn,
      churn_probability: pred ? pred.churn_probability : null,
      risk_level: pred ? pred.risk_level : null,
    };
  });

  res.json({
    page,
    pageSize,
    total,
    totalPages,
    comparison,
    rows,
  });
});

app.get("/api/predictions", (req, res) => {
  if (!store.predictions) {
    return res.status(503).json({
      error: "Predictions mart is missing. Run spark_train.py first.",
    });
  }

  const customerID = String(req.query.customerID || "").trim().toLowerCase();
  const risk = String(req.query.risk || "").trim();
  const sortDir = String(req.query.sort || "desc").toLowerCase() === "asc" ? 1 : -1;
  const page = Math.max(1, Number(req.query.page || 1));
  const pageSize = Math.min(50, Math.max(5, Number(req.query.pageSize || 12)));

  let filtered = store.predictions;
  if (customerID) {
    filtered = filtered.filter((r) =>
      String(r.customerID || "").toLowerCase().includes(customerID)
    );
  }
  if (["High", "Medium", "Low"].includes(risk)) {
    filtered = filtered.filter((r) => r.risk_level === risk);
  }

  // Sort by probability (default descending)
  const sorted = [...filtered].sort((a, b) => {
    const diff = (Number(a.churn_probability) - Number(b.churn_probability)) * sortDir;
    if (diff !== 0) return diff;
    return String(a.customerID).localeCompare(String(b.customerID));
  });

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const rows = sorted.slice((page - 1) * pageSize, page * pageSize);

  res.json({
    page,
    pageSize,
    total,
    totalPages,
    rows,
  });
});

app.get("/api/model", (_req, res) => {
  if (!store.evaluationSummary) {
    return res.status(503).json({
      error: "evaluation_summary.json was not found. Run python spark-pipeline/spark_train.py first.",
    });
  }
  res.json(store.evaluationSummary);
});

app.get("/api/feature-importance.png", (_req, res) => {
  if (!fs.existsSync(PATHS.featurePlot)) {
    return res.status(404).json({ error: "feature_importance.png is missing." });
  }
  res.sendFile(PATHS.featurePlot);
});

app.get("/api/segments", (_req, res) => {
  if (!store.clusteringSummary) {
    return res.status(503).json({
      error: "clustering_summary.json is not yet generated. Run spark_clustering.py first.",
    });
  }
  res.json(store.clusteringSummary);
});

app.listen(PORT, () => {
  console.log(`[Express] Decoupled Analytical Dashboard API listening on http://localhost:${PORT}`);
});
