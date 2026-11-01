const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function request(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function fetchDashboard() {
  try {
    return await request("/api/dashboard");
  } catch (err) {
    const fallback = await fetch("/data/dashboard.json");
    if (fallback.ok) {
      return fallback.json();
    }
    throw err;
  }
}

export function fetchCustomers(params) {
  const query = new URLSearchParams(
    Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== "" && value != null)
    )
  );
  return request(`/api/customers?${query.toString()}`);
}

export async function fetchPredictions(params = {}) {
  const query = new URLSearchParams(
    Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== "" && value != null)
    )
  );

  try {
    return await request(`/api/predictions?${query.toString()}`);
  } catch (err) {
    const fallback = await fetch("/data/predictions.json");
    if (fallback.ok) {
      const allRows = await fallback.json();
      const customerID = String(params.customerID || "").trim().toLowerCase();
      const risk = String(params.risk || "").trim();
      const sortDir = String(params.sort || "desc").toLowerCase() === "asc" ? 1 : -1;
      const page = Math.max(1, Number(params.page || 1));
      const pageSize = Math.min(50, Math.max(5, Number(params.pageSize || 12)));

      let filtered = allRows;
      if (customerID) {
        filtered = filtered.filter((r) =>
          String(r.customerID || "").toLowerCase().includes(customerID)
        );
      }
      if (["High", "Medium", "Low"].includes(risk)) {
        filtered = filtered.filter((r) => r.risk_level === risk);
      }
      filtered.sort((a, b) => (a.churn_probability - b.churn_probability) * sortDir);

      const total = filtered.length;
      const totalPages = Math.max(1, Math.ceil(total / pageSize));
      const rows = filtered.slice((page - 1) * pageSize, page * pageSize);
      return { page, pageSize, total, totalPages, rows };
    }
    throw err;
  }
}

export async function fetchModel() {
  try {
    return await request("/api/model");
  } catch (err) {
    const fallback = await fetch("/data/model.json");
    if (fallback.ok) {
      return fallback.json();
    }
    throw err;
  }
}
