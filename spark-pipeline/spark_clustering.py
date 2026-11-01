"""
Customer Segmentation and Clustering Module using Spark MLlib KMeans and PCA.
Performs silhouette sweep (k=2..7), fits KMeans (k=4, seed=42),
profiles clusters, and produces PCA 2D projections.
"""
from pathlib import Path
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler, StandardScaler, PCA
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.functions import vector_to_array

from config import (
    CUSTOMERS_PARQUET,
    CUSTOMER_SEGMENTS_PARQUET,
    CLUSTERING_SUMMARY_JSON,
    CUSTOMER_CLUSTERS_PNG,
    SEED,
    ensure_dirs,
    write_json,
)
from spark_session import get_spark


def run_clustering():
    """Execute KMeans clustering sweep, final model profiling, and PCA visualization."""
    ensure_dirs()
    spark = get_spark("TelcoChurnClustering")

    print(f"Loading data from {CUSTOMERS_PARQUET}...")
    df = spark.read.parquet(str(CUSTOMERS_PARQUET))

    # Feature preparation
    # ContractCode: Month-to-month 0, One year 1, Two year 2
    df_features = df.withColumn(
        "ContractCode",
        F.when(F.col("Contract") == "Month-to-month", 0.0)
        .when(F.col("Contract") == "One year", 1.0)
        .when(F.col("Contract") == "Two year", 2.0)
        .otherwise(0.0),
    )

    feature_cols = [
        "tenure",
        "MonthlyCharges",
        "TotalCharges",
        "TotalServices",
        "ContractCode",
    ]

    assembler = VectorAssembler(inputCols=feature_cols, outputCol="raw_cluster_features")
    scaler = StandardScaler(
        inputCol="raw_cluster_features",
        outputCol="features",
        withMean=True,
        withStd=True,
    )

    vector_df = assembler.transform(df_features)
    scaler_model = scaler.fit(vector_df)
    scaled_df = scaler_model.transform(vector_df).cache()

    evaluator = ClusteringEvaluator(
        featuresCol="features",
        predictionCol="prediction",
        metricName="silhouette",
        distanceMeasure="squaredEuclidean",
    )

    print("\n--- Sweeping k = 2..7 for Silhouette and Cost (WSSSE) ---")
    sweep_results = []
    best_k = 2
    best_silhouette = -1.0

    for k in range(2, 8):
        kmeans = KMeans(
            featuresCol="features",
            predictionCol="prediction",
            k=k,
            seed=SEED,
            maxIter=50,
            initMode="k-means||",
        )
        model = kmeans.fit(scaled_df)
        preds = model.transform(scaled_df)
        silhouette = round(evaluator.evaluate(preds), 4)
        cost = round(model.summary.trainingCost, 2)
        print(f"k={k} | Silhouette={silhouette:.4f} | Training Cost (WSSSE)={cost}")
        sweep_results.append({"k": k, "silhouette": silhouette, "wssse": cost})

        if silhouette > best_silhouette:
            best_silhouette = silhouette
            best_k = k

    print(f"\nSilhouette sweep complete. Best silhouette={best_silhouette:.4f} at k={best_k}.")
    if best_k != 4:
        print(f"Note: k=4 (silhouette={sweep_results[2]['silhouette']:.4f}) is selected per project specification for business domain interpretability.")

    # Final KMeans model with k=4
    print("\n--- Fitting Final KMeans Model (k=4, seed=42) ---")
    final_kmeans = KMeans(
        featuresCol="features",
        predictionCol="cluster",
        k=4,
        seed=SEED,
        maxIter=50,
        initMode="k-means||",
    )
    final_model = final_kmeans.fit(scaled_df)
    clustered_df = final_model.transform(scaled_df)

    # Save customer_segments.parquet
    print(f"Saving customer segments to {CUSTOMER_SEGMENTS_PARQUET}...")
    clustered_df.select(
        "customerID",
        "cluster",
        "tenure",
        "MonthlyCharges",
        "TotalCharges",
        "TotalServices",
        "Contract",
        "Churn",
    ).write.mode("overwrite").parquet(str(CUSTOMER_SEGMENTS_PARQUET))

    # Cluster profiling
    print("\n--- Cluster Profile Summary ---")
    profile_df = clustered_df.groupBy("cluster").agg(
        F.count("*").alias("customer_count"),
        F.round(F.avg("tenure"), 1).alias("avg_tenure"),
        F.round(F.avg("MonthlyCharges"), 2).alias("avg_monthly_charges"),
        F.round(F.avg("TotalCharges"), 2).alias("avg_total_charges"),
        F.round(F.avg("TotalServices"), 2).alias("avg_services"),
        F.round(F.avg("ContractCode"), 2).alias("avg_contract_code"),
        F.round(
            F.avg(F.when(F.col("Churn") == "Yes", 1.0).otherwise(0.0)) * 100, 2
        ).alias("churn_rate_pct"),
    ).sort("cluster")

    profile_records = [row.asDict() for row in profile_df.collect()]
    for p in profile_records:
        print(
            f"Cluster {p['cluster']}: Customers={p['customer_count']}, "
            f"Avg Tenure={p['avg_tenure']} mo, Avg Monthly=${p['avg_monthly_charges']}, "
            f"Avg Services={p['avg_services']}, Churn={p['churn_rate_pct']}%"
        )

    # 2D PCA Projection for Visualization
    print("\nComputing PCA(k=2) projection for cluster visualization...")
    pca = PCA(k=2, inputCol="features", outputCol="pca_features")
    pca_model = pca.fit(scaled_df)
    pca_df = pca_model.transform(clustered_df)

    pca_sample = (
        pca_df.withColumn("pca_x", vector_to_array(F.col("pca_features"))[0])
        .withColumn("pca_y", vector_to_array(F.col("pca_features"))[1])
        .select("customerID", "cluster", "pca_x", "pca_y", "Churn")
        .toPandas()
    )

    plt.figure(figsize=(9, 6))
    palette = sns.color_palette("Set2", 4)
    sns.scatterplot(
        data=pca_sample,
        x="pca_x",
        y="pca_y",
        hue="cluster",
        palette=palette,
        style="Churn",
        alpha=0.6,
        s=40,
    )
    plt.title("Customer Segments — KMeans (k=4) in PCA 2D Space", fontsize=13, pad=12)
    plt.xlabel(f"Principal Component 1 ({pca_model.explainedVariance[0]*100:.1f}% var)")
    plt.ylabel(f"Principal Component 2 ({pca_model.explainedVariance[1]*100:.1f}% var)")
    plt.legend(title="Cluster / Churn", loc="upper right")
    plt.tight_layout()
    plt.savefig(CUSTOMER_CLUSTERS_PNG, dpi=200)
    plt.close()
    print(f"Saved cluster scatter plot to {CUSTOMER_CLUSTERS_PNG}")

    # Write clustering_summary.json
    final_silhouette = round(evaluator.evaluate(clustered_df.withColumn("prediction", F.col("cluster"))), 4)
    cluster_summary = {
        "k": 4,
        "silhouette": final_silhouette,
        "sweep_results": sweep_results,
        "best_sweep_k": best_k,
        "best_sweep_silhouette": best_silhouette,
        "cluster_profiles": profile_records,
        "feature_columns": feature_cols,
    }
    write_json(cluster_summary, CLUSTERING_SUMMARY_JSON)
    print(f"Saved clustering summary to {CLUSTERING_SUMMARY_JSON}")

    scaled_df.unpersist()
    spark.stop()


if __name__ == "__main__":
    run_clustering()
