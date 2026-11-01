"""
Regression Analysis Module targeting MonthlyCharges using Spark MLlib LinearRegression.
Fits ElasticNet and OLS (Ordinary Least Squares with normal solver).
Avoids multicollinear service levels to guarantee non-singular Gram matrix
and exact p-values.
"""
from pathlib import Path
import json
from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.ml.evaluation import RegressionEvaluator

from config import (
    CUSTOMERS_PARQUET,
    REGRESSION_SUMMARY_JSON,
    SEED,
    ensure_dirs,
    write_json,
)
from spark_session import get_spark


def run_regression():
    """Fit ElasticNet and OLS models to explain MonthlyCharges breakdown."""
    ensure_dirs()
    spark = get_spark("TelcoChurnRegression")

    print(f"Loading data from {CUSTOMERS_PARQUET}...")
    df = spark.read.parquet(str(CUSTOMERS_PARQUET))

    # Construct clean indicator features without collinear dummy levels
    df_reg = (
        df.withColumn(
            "PhoneService_yes",
            F.when(F.col("PhoneService") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "MultipleLines_yes",
            F.when(F.col("MultipleLines") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "OnlineSecurity_yes",
            F.when(F.col("OnlineSecurity") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "OnlineBackup_yes",
            F.when(F.col("OnlineBackup") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "DeviceProtection_yes",
            F.when(F.col("DeviceProtection") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "TechSupport_yes",
            F.when(F.col("TechSupport") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "StreamingTV_yes",
            F.when(F.col("StreamingTV") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "StreamingMovies_yes",
            F.when(F.col("StreamingMovies") == "Yes", 1.0).otherwise(0.0),
        )
        .withColumn(
            "InternetService_DSL",
            F.when(F.col("InternetService") == "DSL", 1.0).otherwise(0.0),
        )
        .withColumn(
            "InternetService_FiberOptic",
            F.when(F.col("InternetService") == "Fiber optic", 1.0).otherwise(0.0),
        )
    )

    feature_cols = [
        "PhoneService_yes",
        "MultipleLines_yes",
        "InternetService_DSL",
        "InternetService_FiberOptic",
        "OnlineSecurity_yes",
        "OnlineBackup_yes",
        "DeviceProtection_yes",
        "TechSupport_yes",
        "StreamingTV_yes",
        "StreamingMovies_yes",
    ]

    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
    df_vector = assembler.transform(df_reg).select("features", "MonthlyCharges")

    # 80/20 train/test split
    print("Splitting dataset 80/20 with randomSplit(seed=42)...")
    train, test = df_vector.randomSplit([0.80, 0.20], seed=SEED)
    train.cache()
    test.cache()

    eval_r2 = RegressionEvaluator(
        labelCol="MonthlyCharges", predictionCol="prediction", metricName="r2"
    )
    eval_rmse = RegressionEvaluator(
        labelCol="MonthlyCharges", predictionCol="prediction", metricName="rmse"
    )
    eval_mae = RegressionEvaluator(
        labelCol="MonthlyCharges", predictionCol="prediction", metricName="mae"
    )

    # (a) ElasticNet Linear Regression
    print("\nFitting ElasticNet (regParam=0.3, elasticNetParam=0.8, maxIter=100)...")
    en_lr = LinearRegression(
        featuresCol="features",
        labelCol="MonthlyCharges",
        regParam=0.3,
        elasticNetParam=0.8,
        maxIter=100,
    )
    en_model = en_lr.fit(train)
    en_preds = en_model.transform(test)

    en_r2 = round(eval_r2.evaluate(en_preds), 4)
    en_rmse = round(eval_rmse.evaluate(en_preds), 4)
    en_mae = round(eval_mae.evaluate(en_preds), 4)
    print(f"ElasticNet Test Metrics: R2={en_r2:.4f}, RMSE={en_rmse:.4f}, MAE={en_mae:.4f}")

    # (b) OLS Linear Regression (solver='normal' for exact p-values)
    print("\nFitting OLS (regParam=0.0, solver='normal') for inferential p-values...")
    ols_lr = LinearRegression(
        featuresCol="features",
        labelCol="MonthlyCharges",
        regParam=0.0,
        solver="normal",
    )
    ols_model = ols_lr.fit(train)
    ols_preds = ols_model.transform(test)

    ols_test_r2 = round(eval_r2.evaluate(ols_preds), 4)
    ols_test_rmse = round(eval_rmse.evaluate(ols_preds), 4)
    ols_test_mae = round(eval_mae.evaluate(ols_preds), 4)
    ols_train_r2 = round(ols_model.summary.r2, 4)

    print(f"OLS Train R2={ols_train_r2:.4f} | Test R2={ols_test_r2:.4f}, RMSE={ols_test_rmse:.4f}, MAE={ols_test_mae:.4f}")

    # Extract coefficients, std errors, t-values, and p-values
    summary = ols_model.summary
    p_values = [round(val, 6) for val in summary.pValues]
    t_values = [round(val, 4) for val in summary.tValues]
    std_errs = [round(val, 4) for val in summary.coefficientStandardErrors]
    coeffs = [round(val, 4) for val in ols_model.coefficients.toArray()]

    feature_p_table = []
    print("\n--- OLS Feature Impact & Statistical Significance ---")
    print(f"{'Feature':<28} {'Coeff':>9} {'StdErr':>9} {'t-Stat':>9} {'p-Value':>10}")
    print("-" * 68)
    for i, col_name in enumerate(feature_cols):
        entry = {
            "feature": col_name,
            "coefficient": coeffs[i],
            "std_error": std_errs[i],
            "t_stat": t_values[i],
            "p_value": p_values[i],
            "significant_at_001": p_values[i] < 0.001,
        }
        feature_p_table.append(entry)
        print(
            f"{col_name:<28} {coeffs[i]:>9.4f} {std_errs[i]:>9.4f} "
            f"{t_values[i]:>9.4f} {p_values[i]:>10.6f}"
        )
    print(f"{'Intercept':<28} {ols_model.intercept:>9.4f}")

    # Write regression_summary.json
    regression_summary = {
        "target": "MonthlyCharges",
        "train_rows": train.count(),
        "test_rows": test.count(),
        "elastic_net": {
            "regParam": 0.3,
            "elasticNetParam": 0.8,
            "test_r2": en_r2,
            "test_rmse": en_rmse,
            "test_mae": en_mae,
        },
        "ols": {
            "regParam": 0.0,
            "solver": "normal",
            "train_r2": ols_train_r2,
            "test_r2": ols_test_r2,
            "test_rmse": ols_test_rmse,
            "test_mae": ols_test_mae,
            "intercept": round(ols_model.intercept, 4),
            "coefficients": feature_p_table,
        },
    }
    write_json(regression_summary, REGRESSION_SUMMARY_JSON)
    print(f"\nSaved regression summary to {REGRESSION_SUMMARY_JSON}")

    train.unpersist()
    test.unpersist()
    spark.stop()


if __name__ == "__main__":
    run_regression()
