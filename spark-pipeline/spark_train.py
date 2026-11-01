"""
Model Training and Hold-out Evaluation Pipeline for Telco Churn.
Trains 5 classification models using Spark ML Pipelines and CrossValidator:
1. Logistic Regression (Tuned)
2. Decision Tree Classifier
3. Random Forest Classifier (Tuned - Primary Scoring Model)
4. Gradient-Boosted Tree (GBT) Classifier
5. Linear Support Vector Machine (LinearSVC)

Scores all 7,043 customers, computes hold-out metrics, confusion matrices,
extracts feature importances, and exports marts.
"""
import time
from datetime import datetime, timezone
from pathlib import Path
import json
import matplotlib.pyplot as plt
import pandas as pd

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.feature import (
    StringIndexer,
    OneHotEncoder,
    VectorAssembler,
    StandardScaler,
)
from pyspark.ml.classification import (
    LogisticRegression,
    DecisionTreeClassifier,
    RandomForestClassifier,
    GBTClassifier,
    LinearSVC,
)
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
from pyspark.ml.evaluation import (
    BinaryClassificationEvaluator,
    MulticlassClassificationEvaluator,
)
from pyspark.ml.functions import vector_to_array

from config import (
    CUSTOMERS_PARQUET,
    PREDICTIONS_PARQUET,
    API_PREDICTIONS_JSON,
    SPARK_RF_PIPELINE,
    EVALUATION_SUMMARY_JSON,
    MODEL_COMPARISON_CSV,
    FEATURE_IMPORTANCE_PNG,
    DASHBOARD_SUMMARY_JSON,
    SEED,
    EXPECTED_ROWS,
    HIGH,
    MEDIUM,
    CATEGORICAL_COLS,
    NUMERIC_COLS,
    ensure_dirs,
    write_json,
)
from spark_session import get_spark


def build_preprocessing_stages():
    """
    Build data preprocessing stages for MLlib Pipeline:
    - StringIndexer for 17 categorical columns (handleInvalid="keep")
    - OneHotEncoder for indexed categoricals (handleInvalid="keep")
    - VectorAssembler combining numeric cols + OHE vectors -> "raw_features"
    - StandardScaler withMean=True, withStd=True -> "features"
    Vector dimension = 72.
    """
    # String indexer for each categorical col
    indexers = [
        StringIndexer(
            inputCol=col_name,
            outputCol=f"{col_name}_idx",
            handleInvalid="keep",
        )
        for col_name in CATEGORICAL_COLS
    ]

    # One-hot encoder
    ohe_inputs = [f"{col_name}_idx" for col_name in CATEGORICAL_COLS]
    ohe_outputs = [f"{col_name}_vec" for col_name in CATEGORICAL_COLS]
    ohe = OneHotEncoder(
        inputCols=ohe_inputs,
        outputCols=ohe_outputs,
        handleInvalid="keep",
    )

    # Assembler: numeric + OHE features
    assembler_inputs = NUMERIC_COLS + ohe_outputs
    assembler = VectorAssembler(
        inputCols=assembler_inputs,
        outputCol="raw_features",
        handleInvalid="keep",
    )

    # Standard scaler (mean-centered and unit variance)
    scaler = StandardScaler(
        inputCol="raw_features",
        outputCol="features",
        withMean=True,
        withStd=True,
    )

    return indexers + [ohe, assembler, scaler]


def compute_confusion_matrix_and_metrics(predictions_df: DataFrame):
    """
    Compute confusion matrix [[TN, FP], [FN, TP]] and churn class (1.0)
    precision, recall, and F1 score from prediction and label columns.
    """
    # Map predictions to (prediction, label) counts via Spark SQL groupBy
    rows = (
        predictions_df.groupBy("prediction", "label")
        .count()
        .collect()
    )
    counts = {(int(r["prediction"]), int(r["label"])): int(r["count"]) for r in rows}

    tn = counts.get((0, 0), 0)
    fp = counts.get((1, 0), 0)
    fn = counts.get((0, 1), 0)
    tp = counts.get((1, 1), 0)

    cm = [[tn, fp], [fn, tp]]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        (2.0 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return cm, round(precision, 4), round(recall, 4), round(f1, 4)


def extract_feature_names(model_fitted, train_sample: DataFrame):
    """
    Extract readable feature names from the VectorAssembler metadata inside the pipeline.
    """
    try:
        # Transform a small sample to get output schema metadata
        transformed = model_fitted.transform(train_sample.limit(5))
        metadata = transformed.schema["raw_features"].metadata
        attrs = metadata.get("ml_attr", {}).get("attrs", {})

        feature_map = {}
        for attr_type in ["numeric", "binary", "nominal"]:
            if attr_type in attrs:
                for item in attrs[attr_type]:
                    feature_map[item["idx"]] = item["name"]

        # Ordered list by index
        num_features = len(feature_map)
        ordered_names = [feature_map.get(i, f"feature_{i}") for i in range(num_features)]
        return ordered_names
    except Exception as e:
        print(f"Warning: feature name extraction encountered: {e}")
        return [f"feature_{i}" for i in range(72)]


def train_and_evaluate():
    """Run full stratified ML pipeline, model tuning, hold-out evaluation, and scoring."""
    ensure_dirs()
    spark = get_spark("TelcoChurnTraining")

    print(f"Loading data from {CUSTOMERS_PARQUET}...")
    df = spark.read.parquet(str(CUSTOMERS_PARQUET))

    # Add numeric label column (1.0 for Yes, 0.0 for No)
    # Ensure SeniorCitizen is StringType for categorical indexer consistency
    df_labeled = df.withColumn(
        "label",
        F.when(F.col("Churn") == "Yes", 1.0).otherwise(0.0),
    ).withColumn("SeniorCitizen", F.col("SeniorCitizen").cast(StringType()))

    # Stratified 80/20 train/test split using sampleBy
    print("Performing stratified 80/20 split on raw dataset (seed=42)...")
    train = df_labeled.sampleBy("label", fractions={0.0: 0.80, 1.0: 0.80}, seed=SEED).cache()
    test = df_labeled.join(train.select("customerID"), on="customerID", how="left_anti").cache()

    train_count = train.count()
    test_count = test.count()
    print(f"Split results: Train={train_count}, Test={test_count}, Total={train_count + test_count}")
    print("Note: sampleBy uses Bernoulli sampling per strata, so split size is approximate.")

    # Assert zero customerID overlap and exact row sum
    overlap = train.join(test, "customerID").count()
    assert overlap == 0, f"Data leakage detected! Overlapping customerIDs: {overlap}"
    assert (
        train_count + test_count == EXPECTED_ROWS
    ), f"Row count mismatch: {train_count + test_count} != {EXPECTED_ROWS}"

    # Majority baseline accuracy
    test_non_churn = test.filter(F.col("label") == 0.0).count()
    majority_baseline = round(test_non_churn / test_count, 4)
    print(f"Test set majority-class baseline accuracy: {majority_baseline * 100:.2f}%")

    # Evaluators
    roc_eval = BinaryClassificationEvaluator(
        rawPredictionCol="rawPrediction",
        labelCol="label",
        metricName="areaUnderROC",
    )
    pr_eval = BinaryClassificationEvaluator(
        rawPredictionCol="rawPrediction",
        labelCol="label",
        metricName="areaUnderPR",
    )
    acc_eval = MulticlassClassificationEvaluator(
        predictionCol="prediction", labelCol="label", metricName="accuracy"
    )
    w_prec_eval = MulticlassClassificationEvaluator(
        predictionCol="prediction", labelCol="label", metricName="weightedPrecision"
    )
    w_rec_eval = MulticlassClassificationEvaluator(
        predictionCol="prediction", labelCol="label", metricName="weightedRecall"
    )
    f1_eval = MulticlassClassificationEvaluator(
        predictionCol="prediction", labelCol="label", metricName="f1"
    )

    models_info = []
    trained_pipelines = {}

    # Define model configurations
    # 1. Logistic Regression with CrossValidator
    print("\n--- Model 1: Logistic Regression (Hyperparameter Tuning via 3-Fold CV) ---")
    lr = LogisticRegression(featuresCol="features", labelCol="label", maxIter=50)
    lr_pipeline = Pipeline(stages=build_preprocessing_stages() + [lr])
    lr_param_grid = (
        ParamGridBuilder()
        .addGrid(lr.regParam, [0.001, 0.01, 0.1])
        .addGrid(lr.elasticNetParam, [0.0, 0.5])
        .build()
    )
    lr_cv = CrossValidator(
        estimator=lr_pipeline,
        estimatorParamMaps=lr_param_grid,
        evaluator=roc_eval,
        numFolds=3,
        seed=SEED,
    )
    t0 = time.time()
    lr_cv_model = lr_cv.fit(train)
    fit_time = round(time.time() - t0, 2)
    best_lr = lr_cv_model.bestModel.stages[-1]
    best_lr_params = {
        "regParam": best_lr.getRegParam(),
        "elasticNetParam": best_lr.getElasticNetParam(),
    }
    print(f"LR Fit Time: {fit_time}s | Best Params: {best_lr_params}")
    trained_pipelines["Logistic Regression"] = (lr_cv_model.bestModel, best_lr_params, fit_time)

    # 2. Decision Tree Classifier
    print("\n--- Model 2: Decision Tree Classifier (maxDepth=5, gini) ---")
    dt = DecisionTreeClassifier(
        featuresCol="features", labelCol="label", maxDepth=5, impurity="gini", seed=SEED
    )
    dt_pipeline = Pipeline(stages=build_preprocessing_stages() + [dt])
    t0 = time.time()
    dt_model = dt_pipeline.fit(train)
    fit_time = round(time.time() - t0, 2)
    dt_params = {"maxDepth": 5, "impurity": "gini"}
    print(f"DT Fit Time: {fit_time}s | Params: {dt_params}")
    trained_pipelines["Decision Tree"] = (dt_model, dt_params, fit_time)

    # 3. Random Forest Classifier with CrossValidator
    print("\n--- Model 3: Random Forest Classifier (Primary Scoring Model, 3-Fold CV) ---")
    rf = RandomForestClassifier(
        featuresCol="features",
        labelCol="label",
        featureSubsetStrategy="sqrt",
        seed=SEED,
    )
    rf_pipeline = Pipeline(stages=build_preprocessing_stages() + [rf])
    rf_param_grid = (
        ParamGridBuilder()
        .addGrid(rf.maxDepth, [5, 8])
        .addGrid(rf.numTrees, [50, 100])
        .build()
    )
    rf_cv = CrossValidator(
        estimator=rf_pipeline,
        estimatorParamMaps=rf_param_grid,
        evaluator=roc_eval,
        numFolds=3,
        seed=SEED,
    )
    t0 = time.time()
    rf_cv_model = rf_cv.fit(train)
    fit_time = round(time.time() - t0, 2)
    best_rf = rf_cv_model.bestModel.stages[-1]
    best_rf_params = {
        "maxDepth": int(best_rf.getOrDefault(best_rf.maxDepth)),
        "numTrees": int(best_rf.getOrDefault(best_rf.numTrees)),
        "featureSubsetStrategy": "sqrt",
    }
    print(f"RF Fit Time: {fit_time}s | Best Params: {best_rf_params}")
    trained_pipelines["Random Forest"] = (rf_cv_model.bestModel, best_rf_params, fit_time)

    # 4. Gradient-Boosted Trees (GBT)
    print("\n--- Model 4: Gradient-Boosted Tree Classifier (maxIter=50, maxDepth=5) ---")
    gbt = GBTClassifier(
        featuresCol="features", labelCol="label", maxIter=50, maxDepth=5, seed=SEED
    )
    gbt_pipeline = Pipeline(stages=build_preprocessing_stages() + [gbt])
    t0 = time.time()
    gbt_model = gbt_pipeline.fit(train)
    fit_time = round(time.time() - t0, 2)
    gbt_params = {"maxIter": 50, "maxDepth": 5}
    print(f"GBT Fit Time: {fit_time}s | Params: {gbt_params}")
    trained_pipelines["Gradient Boosted Trees"] = (gbt_model, gbt_params, fit_time)

    # 5. Linear Support Vector Machine (LinearSVC)
    print("\n--- Model 5: Linear Support Vector Machine (maxIter=100, regParam=0.1) ---")
    svc = LinearSVC(
        featuresCol="features", labelCol="label", maxIter=100, regParam=0.1
    )
    svc_pipeline = Pipeline(stages=build_preprocessing_stages() + [svc])
    t0 = time.time()
    svc_model = svc_pipeline.fit(train)
    fit_time = round(time.time() - t0, 2)
    svc_params = {"maxIter": 100, "regParam": 0.1}
    print(f"SVC Fit Time: {fit_time}s | Params: {svc_params}")
    trained_pipelines["Linear SVC"] = (svc_model, svc_params, fit_time)

    # Evaluate all models on raw stratified hold-out test set
    print("\nEvaluating all 5 models on the held-out test set...")
    comparison_rows = []

    for name, (model, params, fit_sec) in trained_pipelines.items():
        preds = model.transform(test)

        # ROC-AUC and PR-AUC use rawPrediction or probability
        roc_auc = round(roc_eval.evaluate(preds), 4)
        pr_auc = round(pr_eval.evaluate(preds), 4)
        acc = round(acc_eval.evaluate(preds), 4)
        w_prec = round(w_prec_eval.evaluate(preds), 4)
        w_rec = round(w_rec_eval.evaluate(preds), 4)
        overall_f1 = round(f1_eval.evaluate(preds), 4)

        cm, churn_prec, churn_rec, churn_f1 = compute_confusion_matrix_and_metrics(preds)

        print(
            f"[{name}] Acc={acc:.4f} | Churn Prec={churn_prec:.4f} | "
            f"Churn Recall={churn_rec:.4f} | Churn F1={churn_f1:.4f} | ROC-AUC={roc_auc:.4f}"
        )

        model_entry = {
            "name": name,
            "accuracy": acc,
            "precision": churn_prec,  # Churn class (1.0) precision
            "recall": churn_rec,        # Churn class (1.0) recall
            "f1": churn_f1,             # Churn class (1.0) F1
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "weighted_precision": w_prec,
            "weighted_recall": w_rec,
            "overall_f1": overall_f1,
            "confusion_matrix": cm,
            "best_params": params,
            "fit_seconds": fit_sec,
        }
        models_info.append(model_entry)

        comparison_rows.append(
            {
                "Model": name,
                "Accuracy": acc,
                "Precision": churn_prec,
                "Recall": churn_rec,
                "F1": churn_f1,
                "ROC-AUC": roc_auc,
                "PR-AUC": pr_auc,
                "FitTime_sec": fit_sec,
            }
        )

    # Write model_comparison.csv
    comp_df = pd.DataFrame(comparison_rows)
    comp_df.to_csv(MODEL_COMPARISON_CSV, index=False)
    print(f"\nSaved model comparison table to {MODEL_COMPARISON_CSV}")

    # Extract Feature Importances from Tuned Random Forest
    rf_best_pipeline, _, _ = trained_pipelines["Random Forest"]
    rf_stage = rf_best_pipeline.stages[-1]
    importances = rf_stage.featureImportances.toArray().tolist()

    feature_names = extract_feature_names(rf_best_pipeline, train)
    feat_imp_pairs = sorted(
        zip(feature_names, importances), key=lambda x: x[1], reverse=True
    )
    top10_pairs = [[name, round(val, 6)] for name, val in feat_imp_pairs[:10]]

    print("\nRandom Forest Top 10 Features:")
    for rank, (name, val) in enumerate(top10_pairs, 1):
        print(f" {rank:2d}. {name:<35} {val:.6f}")

    # Plot top 10 feature importance
    plt.figure(figsize=(9, 5))
    top10_names = [p[0] for p in top10_pairs][::-1]
    top10_vals = [p[1] for p in top10_pairs][::-1]
    plt.barh(range(len(top10_names)), top10_vals, color="#6366f1", edgecolor="none")
    plt.yticks(range(len(top10_names)), top10_names, fontsize=9)
    plt.xlabel("Predictive Contribution / Gini Importance", fontsize=10)
    plt.title("Random Forest — Top 10 Features (Spark MLlib Pipeline)", fontsize=12, pad=12)
    plt.tight_layout()
    plt.savefig(FEATURE_IMPORTANCE_PNG, dpi=200)
    plt.close()
    print(f"Saved feature importance chart to {FEATURE_IMPORTANCE_PNG}")

    # Save Random Forest PipelineModel
    print(f"Saving tuned Random Forest PipelineModel to {SPARK_RF_PIPELINE}...")
    rf_best_pipeline.write().overwrite().save(str(SPARK_RF_PIPELINE))

    # Score ALL 7,043 customers
    print("\nScoring all 7,043 customers with tuned Random Forest PipelineModel...")
    full_scored = rf_best_pipeline.transform(df_labeled)

    # Extract churn probability: probability vector index 1
    # Add split column, risk_level, predicted_churn, revenue_at_risk
    train_ids = train.select("customerID").withColumn("in_train", F.lit(1))

    scored_curated = (
        full_scored.join(train_ids, "customerID", "left")
        .withColumn(
            "split",
            F.when(F.col("in_train") == 1, "train").otherwise("test"),
        )
        .withColumn(
            "churn_probability",
            F.round(vector_to_array(F.col("probability"))[1], 4),
        )
        .withColumn(
            "predicted_churn",
            F.when(F.col("churn_probability") >= 0.5, "Yes").otherwise("No"),
        )
        .withColumn(
            "risk_level",
            F.when(F.col("churn_probability") >= HIGH, "High")
            .when(F.col("churn_probability") >= MEDIUM, "Medium")
            .otherwise("Low"),
        )
        .withColumn(
            "revenue_at_risk",
            F.round(F.col("churn_probability") * F.col("MonthlyCharges"), 2),
        )
        .withColumn("model_used", F.lit("Random Forest (PySpark)"))
        .withColumn("scored_at", F.lit(datetime.now(timezone.utc).isoformat()))
    )

    # Target columns per specification
    export_cols = [
        "customerID",
        "churn_probability",
        "predicted_churn",
        "risk_level",
        "Churn",
        "MonthlyCharges",
        "tenure",
        "Contract",
        "InternetService",
        "revenue_at_risk",
        "split",
        "model_used",
        "scored_at",
    ]
    predictions_final = scored_curated.select(export_cols)

    # Assertions
    pred_count = predictions_final.count()
    print(f"Scored records count: {pred_count}")
    assert (
        pred_count == EXPECTED_ROWS
    ), f"Expected {EXPECTED_ROWS} scored rows, got {pred_count}"

    prob_stats = predictions_final.select(
        F.min("churn_probability").alias("min_p"),
        F.max("churn_probability").alias("max_p"),
    ).collect()[0]
    print(f"Probability range: [{prob_stats['min_p']}, {prob_stats['max_p']}]")
    assert 0.0 <= prob_stats["min_p"] and prob_stats["max_p"] <= 1.0, "Invalid probability range!"

    # Write predictions.parquet
    print(f"Writing {PREDICTIONS_PARQUET}...")
    predictions_final.write.mode("overwrite").parquet(str(PREDICTIONS_PARQUET))

    # Write api_exports/predictions.json sorted by churn_probability descending
    print(f"Writing {API_PREDICTIONS_JSON} (sorted by churn_probability desc)...")
    pred_pdf = predictions_final.sort(F.col("churn_probability").desc()).toPandas()
    pred_pdf.to_json(str(API_PREDICTIONS_JSON), orient="records", indent=2)

    # Risk breakdown stats
    risk_summary = {
        r["risk_level"]: int(r["count"])
        for r in predictions_final.groupBy("risk_level").count().collect()
    }
    high_count = risk_summary.get("High", 0)
    med_count = risk_summary.get("Medium", 0)
    low_count = risk_summary.get("Low", 0)
    print(f"Risk breakdown: High={high_count}, Medium={med_count}, Low={low_count}")

    avg_prob = float(
        predictions_final.select(F.avg("churn_probability")).collect()[0][0]
    )
    monthly_rev_at_risk = float(
        predictions_final.select(F.sum("revenue_at_risk")).collect()[0][0]
    )

    # Write reports/evaluation_summary.json
    eval_summary = {
        "selected_model": "Random Forest",
        "scoring_model": "Random Forest",
        "test_size": test_count,
        "train_size": train_count,
        "majority_baseline_accuracy": majority_baseline,
        "churn_prevalence": round(
            df_labeled.filter(F.col("label") == 1.0).count() / EXPECTED_ROWS, 5
        ),
        "split": {
            "strategy": "Stratified Bernoulli via sampleBy",
            "seed": SEED,
            "train_fraction": 0.8,
            "train_rows": train_count,
            "test_rows": test_count,
            "total_rows": EXPECTED_ROWS,
        },
        "models": models_info,
        "top_features": [
            {"rank": i + 1, "feature": name, "importance": val}
            for i, (name, val) in enumerate(top10_pairs)
        ],
        "feature_importance_top10": top10_pairs,  # Frontend backward compatibility
    }
    write_json(eval_summary, EVALUATION_SUMMARY_JSON)
    print(f"Saved evaluation summary to {EVALUATION_SUMMARY_JSON}")

    # Update dashboard_summary.json with ML predictions summary
    if DASHBOARD_SUMMARY_JSON.exists():
        with open(DASHBOARD_SUMMARY_JSON, "r", encoding="utf-8") as f:
            dash_data = json.load(f)
    else:
        dash_data = {}

    dash_data.update(
        {
            "highRiskCount": high_count,
            "averageProbability": round(avg_prob, 4),
            "avgChurnProbability": round(avg_prob, 4),
            "monthlyRevenueAtRisk": round(monthly_rev_at_risk, 2),
            "modelUsed": "Random Forest (PySpark)",
            "scoredAt": datetime.now(timezone.utc).isoformat(),
            "riskCounts": {
                "High": high_count,
                "Medium": med_count,
                "Low": low_count,
            },
            "riskBreakdown": {
                "High": high_count,
                "Medium": med_count,
                "Low": low_count,
            },
        }
    )
    write_json(dash_data, DASHBOARD_SUMMARY_JSON)
    print(f"Updated {DASHBOARD_SUMMARY_JSON} with ML risk metrics.")

    train.unpersist()
    test.unpersist()
    spark.stop()


if __name__ == "__main__":
    train_and_evaluate()
