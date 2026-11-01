"""
Configuration, path definitions, constants, and feature engineering
for the Telco Churn Spark analytics pipeline.
"""
from pathlib import Path
import json
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# Base paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "raw" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
PROCESSED_DIR = DATA_DIR / "processed"
CUSTOMERS_PARQUET = PROCESSED_DIR / "customers.parquet"
CUSTOMERS_CSV_DIR = PROCESSED_DIR / "customers_csv"
PREDICTIONS_PARQUET = PROCESSED_DIR / "predictions.parquet"
ANALYTICS_DIR = PROCESSED_DIR / "analytics"
CONTRACT_CHURN_PARQUET = ANALYTICS_DIR / "contract_churn.parquet"
CUSTOMER_SEGMENTS_PARQUET = ANALYTICS_DIR / "customer_segments.parquet"
DASHBOARD_SUMMARY_JSON = ANALYTICS_DIR / "dashboard_summary.json"

API_EXPORTS_DIR = PROCESSED_DIR / "api_exports"
API_CUSTOMERS_JSON = API_EXPORTS_DIR / "customers.json"
API_PREDICTIONS_JSON = API_EXPORTS_DIR / "predictions.json"

MODELS_DIR = ROOT / "models"
SPARK_RF_PIPELINE = MODELS_DIR / "spark_rf_pipeline"

REPORTS_DIR = ROOT / "reports"
EVALUATION_SUMMARY_JSON = REPORTS_DIR / "evaluation_summary.json"
MODEL_COMPARISON_CSV = REPORTS_DIR / "model_comparison.csv"
REGRESSION_SUMMARY_JSON = REPORTS_DIR / "regression_summary.json"
CLUSTERING_SUMMARY_JSON = REPORTS_DIR / "clustering_summary.json"
CORRELATION_MATRIX_JSON = REPORTS_DIR / "correlation_matrix.json"
FEATURE_IMPORTANCE_PNG = REPORTS_DIR / "feature_importance.png"
CORRELATION_HEATMAP_PNG = REPORTS_DIR / "correlation_heatmap.png"
CUSTOMER_CLUSTERS_PNG = REPORTS_DIR / "customer_clusters.png"

# Constants
SEED = 42
TRAIN_FRACTION = 0.8
EXPECTED_ROWS = 7043
HIGH = 0.60
MEDIUM = 0.30

# Column specifications
ID_COL = "customerID"
TARGET_COL = "Churn"

SERVICES_COLS = [
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
]

CATEGORICAL_COLS = [
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
    "TenureGroup",
]

NUMERIC_COLS = [
    "tenure",
    "MonthlyCharges",
    "TotalCharges",
    "AvgMonthlySpend",
    "ChargeDifference",
    "TotalServices",
    "StreamingRatio",
    "TenureRatio",
]


def ensure_dirs():
    """Ensure all required project directories exist."""
    for d in [
        DATA_DIR / "raw",
        PROCESSED_DIR,
        ANALYTICS_DIR,
        API_EXPORTS_DIR,
        MODELS_DIR,
        REPORTS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def write_json(data, path):
    """Write data to a JSON file using default=str and indent=2."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def add_engineered_features(df: DataFrame) -> DataFrame:
    """
    Row-level feature engineering without data leakage.
    - AvgMonthlySpend = TotalCharges / (tenure + 1)
    - ChargeDifference = MonthlyCharges - AvgMonthlySpend
    - TotalServices = count of 'Yes' in 6 add-ons
    - StreamingRatio = (StreamingTV=Yes + StreamingMovies=Yes) / (TotalServices + 1)
    - TenureRatio = tenure / 72.0
    - TenureGroup = bins 0-12, 13-24, 25-48, 49-72
    """
    # TotalServices: sum of indicators for the 6 add-on services
    services_expr = sum(
        F.when(F.col(c) == "Yes", 1).otherwise(0) for c in SERVICES_COLS
    )

    streaming_expr = (
        F.when(F.col("StreamingTV") == "Yes", 1).otherwise(0)
        + F.when(F.col("StreamingMovies") == "Yes", 1).otherwise(0)
    )

    df_feat = (
        df.withColumn(
            "AvgMonthlySpend",
            F.round(F.col("TotalCharges") / (F.col("tenure") + 1.0), 4),
        )
        .withColumn(
            "ChargeDifference",
            F.round(F.col("MonthlyCharges") - F.col("AvgMonthlySpend"), 4),
        )
        .withColumn("TotalServices", services_expr)
        .withColumn(
            "StreamingRatio",
            F.round(streaming_expr / (F.col("TotalServices") + 1.0), 4),
        )
        .withColumn(
            "TenureRatio",
            F.round(F.col("tenure") / 72.0, 4),
        )
        .withColumn(
            "TenureGroup",
            F.when(F.col("tenure") <= 12, "0-12")
            .when(F.col("tenure") <= 24, "13-24")
            .when(F.col("tenure") <= 48, "25-48")
            .otherwise("49-72"),
        )
    )
    return df_feat

