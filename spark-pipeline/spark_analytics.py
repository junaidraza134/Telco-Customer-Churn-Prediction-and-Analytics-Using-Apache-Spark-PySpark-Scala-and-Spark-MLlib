"""
Analytics and Aggregation Module using Spark SQL and Spark MLlib Correlation.
Computes KPIs, churn rate by demographics/services, caching benchmark,
Pearson correlation matrix, and visualization heatmaps.
"""
import time
from pathlib import Path
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

from pyspark.ml.stat import Correlation
from pyspark.ml.feature import VectorAssembler
from pyspark.sql import functions as F

from config import (
    CUSTOMERS_PARQUET,
    CONTRACT_CHURN_PARQUET,
    DASHBOARD_SUMMARY_JSON,
    CORRELATION_MATRIX_JSON,
    CORRELATION_HEATMAP_PNG,
    ensure_dirs,
    write_json,
)
from spark_session import get_spark


def run_analytics():
    """Run descriptive analytics, Spark SQL queries, and correlation analysis."""
    ensure_dirs()
    spark = get_spark("TelcoChurnAnalytics")

    print(f"Reading curated dataset from {CUSTOMERS_PARQUET}...")
    df = spark.read.parquet(str(CUSTOMERS_PARQUET))
    df.createOrReplaceTempView("customers")

    # 1. Global KPIs
    print("Computing global KPIs via Spark SQL...")
    kpi_df = spark.sql(
        """
        SELECT
            COUNT(*) AS totalCustomers,
            SUM(CASE WHEN Churn = 'Yes' THEN 1 ELSE 0 END) AS churnedCount,
            SUM(CASE WHEN Churn = 'No' THEN 1 ELSE 0 END) AS retainedCount,
            CAST(AVG(CASE WHEN Churn = 'Yes' THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS churnRate
        FROM customers
        """
    )
    kpis = kpi_df.collect()[0].asDict()
    print(f"KPIs: Total={kpis['totalCustomers']}, Churned={kpis['churnedCount']} "
          f"({kpis['churnRate'] * 100:.2f}%), Retained={kpis['retainedCount']}")

    # 2. Churn by Contract
    print("Computing churn by Contract...")
    contract_df = spark.sql(
        """
        SELECT
            Contract AS contract,
            COUNT(*) AS customers,
            SUM(CASE WHEN Churn = 'Yes' THEN 1 ELSE 0 END) AS churned,
            CAST(AVG(CASE WHEN Churn = 'Yes' THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS churnRate
        FROM customers
        GROUP BY Contract
        ORDER BY customers DESC
        """
    )
    print("Contract query Catalyst Execution Plan (df.explain(True)):")
    contract_df.explain(True)

    # Save contract_churn.parquet
    print(f"Saving contract churn to {CONTRACT_CHURN_PARQUET}...")
    contract_df.write.mode("overwrite").parquet(str(CONTRACT_CHURN_PARQUET))
    contract_churn_records = [row.asDict() for row in contract_df.collect()]

    # 3. Churn by InternetService
    internet_df = spark.sql(
        """
        SELECT
            InternetService AS internetService,
            COUNT(*) AS customers,
            SUM(CASE WHEN Churn = 'Yes' THEN 1 ELSE 0 END) AS churned,
            CAST(AVG(CASE WHEN Churn = 'Yes' THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS churnRate
        FROM customers
        GROUP BY InternetService
        ORDER BY customers DESC
        """
    )
    internet_churn_records = [row.asDict() for row in internet_df.collect()]

    # 4. Churn by TenureGroup
    tenure_group_df = spark.sql(
        """
        SELECT
            TenureGroup AS tenureGroup,
            COUNT(*) AS customers,
            SUM(CASE WHEN Churn = 'Yes' THEN 1 ELSE 0 END) AS churned,
            CAST(AVG(CASE WHEN Churn = 'Yes' THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS churnRate
        FROM customers
        GROUP BY TenureGroup
        ORDER BY tenureGroup ASC
        """
    )
    tenure_group_records = [row.asDict() for row in tenure_group_df.collect()]

    # 5. Churn by PaymentMethod
    payment_df = spark.sql(
        """
        SELECT
            PaymentMethod AS paymentMethod,
            COUNT(*) AS customers,
            SUM(CASE WHEN Churn = 'Yes' THEN 1 ELSE 0 END) AS churned,
            CAST(AVG(CASE WHEN Churn = 'Yes' THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS churnRate
        FROM customers
        GROUP BY PaymentMethod
        ORDER BY customers DESC
        """
    )
    payment_churn_records = [row.asDict() for row in payment_df.collect()]

    # 6. Caching Benchmark: 5 repeated groupBy queries
    print("Running Caching Benchmark (5 repeated aggregations)...")
    # Fresh unpersisted dataframe for fair benchmark
    uncached_df = spark.read.parquet(str(CUSTOMERS_PARQUET))

    # Uncached timing
    t0 = time.perf_counter()
    for _ in range(5):
        uncached_df.groupBy("Contract", "InternetService").agg(
            F.count("*").alias("count"),
            F.avg("MonthlyCharges").alias("avg_monthly"),
            F.avg("TotalCharges").alias("avg_total"),
        ).collect()
    uncached_seconds = round(time.perf_counter() - t0, 4)

    # Cached timing
    cached_df = spark.read.parquet(str(CUSTOMERS_PARQUET)).cache()
    cached_df.count()  # Materialize cache into memory
    t0 = time.perf_counter()
    for _ in range(5):
        cached_df.groupBy("Contract", "InternetService").agg(
            F.count("*").alias("count"),
            F.avg("MonthlyCharges").alias("avg_monthly"),
            F.avg("TotalCharges").alias("avg_total"),
        ).collect()
    cached_seconds = round(time.perf_counter() - t0, 4)
    cached_df.unpersist()

    print(f"Benchmark Results: Uncached={uncached_seconds}s, Cached={cached_seconds}s, "
          f"Speedup={uncached_seconds / max(cached_seconds, 0.001):.2f}x")

    # 7. Pearson Correlation via Spark MLlib
    print("Computing Pearson correlation matrix via Spark MLlib Correlation.corr...")
    corr_cols = [
        "tenure",
        "MonthlyCharges",
        "TotalCharges",
        "AvgMonthlySpend",
        "ChargeDifference",
    ]
    assembler = VectorAssembler(inputCols=corr_cols, outputCol="corr_features")
    df_vector = assembler.transform(df).select("corr_features")

    corr_matrix_row = Correlation.corr(df_vector, "corr_features", "pearson").collect()[0]
    corr_matrix_dense = corr_matrix_row[0].toArray().tolist()

    # Save correlation matrix JSON
    corr_json_data = {
        "columns": corr_cols,
        "matrix": [[round(val, 4) for val in row] for row in corr_matrix_dense],
    }
    write_json(corr_json_data, CORRELATION_MATRIX_JSON)
    print(f"Saved correlation matrix to {CORRELATION_MATRIX_JSON}")

    # Plot correlation heatmap using seaborn
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        np.array(corr_matrix_dense),
        annot=True,
        fmt=".3f",
        cmap="coolwarm",
        xticklabels=corr_cols,
        yticklabels=corr_cols,
        vmin=-1,
        vmax=1,
    )
    plt.title("Pearson Correlation Heatmap (Spark MLlib)", fontsize=13, pad=12)
    plt.tight_layout()
    plt.savefig(CORRELATION_HEATMAP_PNG, dpi=200)
    plt.close()
    print(f"Saved correlation heatmap to {CORRELATION_HEATMAP_PNG}")

    # 8. Write analytics/dashboard_summary.json
    dashboard_summary = {
        "kpis": kpis,
        "totalCustomers": kpis["totalCustomers"],
        "churnedCount": kpis["churnedCount"],
        "retainedCount": kpis["retainedCount"],
        "churnRate": kpis["churnRate"],
        "contractChurn": contract_churn_records,
        "churnByContract": contract_churn_records,
        "internetChurn": internet_churn_records,
        "tenureGroupChurn": tenure_group_records,
        "paymentChurn": payment_churn_records,
        "cachingBenchmarkSeconds": {
            "uncached": uncached_seconds,
            "cached": cached_seconds,
            "speedup": round(uncached_seconds / max(cached_seconds, 0.001), 2),
        },
    }
    write_json(dashboard_summary, DASHBOARD_SUMMARY_JSON)
    print(f"Saved dashboard summary to {DASHBOARD_SUMMARY_JSON}")

    spark.stop()


if __name__ == "__main__":
    run_analytics()
