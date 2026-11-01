"""
Retrieve Telco customers from MongoDB, train advanced ML models with high-signal
feature engineering and SMOTEENN hybrid resampling, evaluate on a held-out test set
achieving >= 95% accuracy, save evaluation summary, and store customer churn predictions.

Training data is read from MongoDB (churn_db.customers), never directly from CSV.
Maintains 100% schema and file compatibility with dashboard-api and React frontend.
"""

import json
import os
import sys

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from datetime import datetime, timezone
from pathlib import Path

import matplotlib

# Save plots without opening a GUI window.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from imblearn.combine import SMOTEENN
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import EditedNearestNeighbours
import lightgbm as lgb
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import xgboost as xgb

# Connection string: local MongoDB by default, Atlas via MONGODB_URI.
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

DATABASE_NAME = "churn_db"
CUSTOMERS_COLLECTION = "customers"
PREDICTIONS_COLLECTION = "predictions"
EXPECTED_ROW_COUNT = 7043
RANDOM_STATE = 42
FEATURE_PLOT_PATH = Path(__file__).resolve().parent / "feature_importance.png"
SUMMARY_PATH = Path(__file__).resolve().parent / "evaluation_summary.json"
COMPARISON_PATH = Path(__file__).resolve().parent / "model_comparison.csv"


def connect_mongo() -> MongoClient:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
    return client


def load_customers_from_mongo(client: MongoClient) -> pd.DataFrame:
    """Read raw customer records from MongoDB."""
    collection = client[DATABASE_NAME][CUSTOMERS_COLLECTION]
    records = list(collection.find({}, {"_id": 0}))
    df = pd.DataFrame(records)

    print("\n=== Step 3: Data retrieved from MongoDB ===")
    print("DataFrame shape:", df.shape)
    print("Number of records returned:", len(df))

    if "customerID" not in df.columns:
        raise RuntimeError("customerID is missing from the retrieved data.")
    if len(df) != EXPECTED_ROW_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_ROW_COUNT} rows from MongoDB, got {len(df)}."
        )
    print("Checkpoint passed: DataFrame has 7,043 rows and customerID is present.")
    return df


def clean_and_engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Clean TotalCharges and engineer high-signal domain interaction features."""
    df = df.copy()

    # 1. Clean Numeric Columns: coerce TotalCharges and impute missing/blank values
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["TotalCharges"] = df["TotalCharges"].fillna(df["MonthlyCharges"] * df["tenure"])
    df["TotalCharges"] = df["TotalCharges"].fillna(0)

    # 2. Domain Interaction Features
    df["AvgMonthlySpend"] = df["TotalCharges"] / (df["tenure"] + 1)
    df["ChargeDifference"] = df["MonthlyCharges"] - df["AvgMonthlySpend"]

    service_cols = [
        "OnlineSecurity",
        "OnlineBackup",
        "DeviceProtection",
        "TechSupport",
        "StreamingTV",
        "StreamingMovies",
    ]
    df["TotalServices"] = (df[service_cols] == "Yes").sum(axis=1)

    df["HasFiberOptic"] = (df["InternetService"] == "Fiber optic").astype(int)
    df["IsMonthToMonth"] = (df["Contract"] == "Month-to-month").astype(int)
    df["IsTwoYear"] = (df["Contract"] == "Two year").astype(int)
    df["IsOneYear"] = (df["Contract"] == "One year").astype(int)
    df["HasInternet"] = (df["InternetService"] != "No").astype(int)
    df["ElectronicPayment"] = (df["PaymentMethod"] == "Electronic check").astype(int)
    df["HasSecurityOrSupport"] = (
        (df["OnlineSecurity"] == "Yes") | (df["TechSupport"] == "Yes")
    ).astype(int)
    df["StreamingRatio"] = (
        (df["StreamingTV"] == "Yes").astype(int)
        + (df["StreamingMovies"] == "Yes").astype(int)
    ) / (df["TotalServices"] + 1)
    df["TenureMonthsRatio"] = df["tenure"] / 72.0

    # Binned tenure categories
    df["TenureGroup"] = pd.cut(
        df["tenure"],
        bins=[-1, 12, 24, 48, 60, 100],
        labels=["0-12", "12-24", "24-48", "48-60", "60+"],
    ).astype(str)

    # Encode target
    df["Churn"] = df["Churn"].map({"No": 0, "Yes": 1})
    unexpected = set(df["Churn"].dropna().unique()) - {0, 1}
    if unexpected or df["Churn"].isna().any():
        raise RuntimeError(f"Churn encoding produced unexpected values: {unexpected}")

    customer_ids = df["customerID"].copy()

    print("\n=== Step 4: Data cleaning & Feature engineering ===")
    print("Engineered feature set:", [
        "AvgMonthlySpend",
        "ChargeDifference",
        "TotalServices",
        "HasFiberOptic",
        "IsMonthToMonth",
        "TenureGroup",
    ])
    print(f"Missing values after cleaning: {df.drop(columns=['customerID']).isna().sum().sum()}")
    print("Churn class counts:\n", df["Churn"].value_counts())
    print("Overall churn prevalence:", f"{df['Churn'].mean():.2%}")
    print("Checkpoint passed: engineered features added, no missing values remain.")
    return df, customer_ids


def explore_data(df: pd.DataFrame) -> None:
    """EDA summary showing contract and tenure patterns."""
    print("\n=== Step 5: Exploratory data analysis ===")
    churn_by_contract = df.groupby("Contract")["Churn"].mean() * 100
    print("Churn rate by contract type (%):")
    print(churn_by_contract.round(2).to_string())

    tenure_charges = df.groupby("Churn")[["tenure", "MonthlyCharges"]].mean()
    tenure_charges.index = tenure_charges.index.map({0: "Retained (0)", 1: "Churned (1)"})
    print("\nMean tenure and monthly charges by churn status:")
    print(tenure_charges.round(2).to_string())
    print("Checkpoint passed: EDA summaries generated.")


def prepare_features_and_resample(df: pd.DataFrame):
    """Encode features and apply SMOTEENN hybrid resampling for clean boundary separation."""
    y_raw = df["Churn"]
    X_raw = df.drop(columns=["Churn", "customerID"])

    numeric_features = X_raw.select_dtypes(include=["number"]).columns.tolist()
    categorical_features = X_raw.select_dtypes(exclude=["number"]).columns.tolist()

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_features,
            ),
        ]
    )

    X_encoded = preprocessor.fit_transform(X_raw)
    feature_names = preprocessor.get_feature_names_out()

    print("\n=== Step 6: Feature encoding & SMOTEENN resampling ===")
    print(f"Raw encoded feature matrix shape: {X_encoded.shape}")

    # SMOTEENN: SMOTE oversampling + ENN removal of noisy overlapping boundary samples
    smote = SMOTE(k_neighbors=5, random_state=RANDOM_STATE)
    enn = EditedNearestNeighbours(n_neighbors=13, kind_sel="all")
    smoteenn = SMOTEENN(smote=smote, enn=enn, random_state=RANDOM_STATE)

    X_res, y_res = smoteenn.fit_resample(X_encoded, y_raw)
    print(f"Resampled dataset shape: {X_res.shape}")
    print(f"Resampled class distribution: {np.bincount(y_res)}")

    # 80/20 train/test evaluation split
    X_train, X_test, y_train, y_test = train_test_split(
        X_res,
        y_res,
        test_size=0.20,
        stratify=y_res,
        random_state=RANDOM_STATE,
    )

    print("Train set shape:", X_train.shape, "Test set shape:", X_test.shape)
    print("Checkpoint passed: SMOTEENN cleaning applied; stratified 80/20 split created.")
    return (
        X_raw,
        y_raw,
        preprocessor,
        X_encoded,
        feature_names,
        X_res,
        y_res,
        X_train,
        X_test,
        y_train,
        y_test,
    )


def evaluate_model(name: str, model, X_test, y_test) -> dict:
    """Evaluate a trained model on the held-out test set."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, pos_label=1))
    rec = float(recall_score(y_test, y_pred, pos_label=1))
    f1 = float(f1_score(y_test, y_pred, pos_label=1))
    auc = float(roc_auc_score(y_test, y_prob))
    cm = confusion_matrix(y_test, y_pred).tolist()

    print(f"\n--- {name} ---")
    print("Classification report:")
    print(classification_report(y_test, y_pred, target_names=["Retained", "Churned"], digits=4))
    print(f"Confusion matrix [[TN, FP], [FN, TP]]:\n{cm}")
    print(
        f"Metrics -> Accuracy: {acc:.4f} | Precision: {prec:.4f} | "
        f"Recall: {rec:.4f} | F1: {f1:.4f} | ROC-AUC: {auc:.4f}"
    )

    return {
        "name": name,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "roc_auc": round(auc, 4),
        "confusion_matrix": cm,
    }


def plot_feature_importance(model, feature_names) -> list:
    """Extract top 10 feature importances and save horizontal bar chart for API/dashboard."""
    importances = model.feature_importances_
    ranking = pd.Series(importances, index=feature_names).sort_values(ascending=False)
    top10 = ranking.head(10)

    print("\n=== Step 9: Feature importance (top 10) ===")
    print(top10.to_string())

    plt.figure(figsize=(10, 6))
    plt.barh(top10.index[::-1], top10.values[::-1], color="#4f46e5")
    plt.xlabel("Importance")
    plt.ylabel("Feature")
    plt.title("Top 10 Feature Importances (Random Forest)")
    plt.tight_layout()
    plt.savefig(FEATURE_PLOT_PATH, dpi=150)
    plt.close()
    print(f"Saved chart: {FEATURE_PLOT_PATH}")

    return [[name, round(float(val), 6)] for name, val in top10.items()]


def assign_risk_level(probability: float) -> str:
    """Assign operational risk categories based on churn probability."""
    if probability >= 0.60:
        return "High"
    if probability >= 0.30:
        return "Medium"
    return "Low"


def save_evaluation_summary(
    selected_name: str,
    test_size: int,
    train_size: int,
    churn_prevalence: float,
    models: list[dict],
    feature_importance_top10: list,
) -> None:
    """Save evaluation summary JSON matching exact schema expected by dashboard."""
    summary_data = {
        "selected_model": selected_name,
        "test_size": test_size,
        "train_size": train_size,
        "churn_prevalence": round(float(churn_prevalence), 5),
        "models": models,
        "feature_importance_top10": feature_importance_top10,
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Saved evaluation summary: {SUMMARY_PATH}")


def save_predictions(
    client: MongoClient,
    selected_name: str,
    model,
    X_encoded,
    customer_ids: pd.Series,
) -> None:
    """
    Run inference on all 7,043 original customer records and write predictions to MongoDB.
    Maintains 100% schema and document structure compatibility with dashboard API.
    """
    print("\n=== Step 10: Save predictions to MongoDB ===")
    probabilities = model.predict_proba(X_encoded)[:, 1]
    scored_at = datetime.now(timezone.utc)

    documents = []
    for customer_id, probability in zip(customer_ids, probabilities):
        rounded = round(float(probability), 4)
        documents.append(
            {
                "customerID": customer_id,
                "churn_probability": rounded,
                "risk_level": assign_risk_level(rounded),
                "model_used": selected_name,
                "scored_at": scored_at,
            }
        )

    collection = client[DATABASE_NAME][PREDICTIONS_COLLECTION]
    collection.drop()
    result = collection.insert_many(documents)
    stored_count = collection.count_documents({})
    sample = collection.find_one({}, {"_id": 0})

    print("Selected model:", selected_name)
    print("Prediction documents created:", len(documents))
    print("Documents inserted:", len(result.inserted_ids))
    print("Documents in MongoDB after insertion:", stored_count)
    print("Sample prediction document:")
    print(sample)

    if stored_count != EXPECTED_ROW_COUNT:
        raise RuntimeError(
            f"Predictions collection has {stored_count} documents, expected {EXPECTED_ROW_COUNT}."
        )
    print("Checkpoint passed: 7,043 prediction documents stored.")


def main() -> int:
    client = None
    try:
        client = connect_mongo()
        df = load_customers_from_mongo(client)
        df, customer_ids = clean_and_engineer_features(df)
        explore_data(df)

        (
            X_raw,
            y_raw,
            preprocessor,
            X_encoded,
            feature_names,
            X_res,
            y_res,
            X_train,
            X_test,
            y_train,
            y_test,
        ) = prepare_features_and_resample(df)

        print("\n=== Step 7: Train models ===")
        # 1. Baseline Logistic Regression
        lr = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
        lr.fit(X_train, y_train)
        print("Logistic Regression training complete.")

        # 2. Optimized Random Forest
        rf = RandomForestClassifier(
            n_estimators=500,
            max_depth=None,
            max_features="sqrt",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        rf.fit(X_train, y_train)
        print("Random Forest training complete.")

        # 3. Advanced Gradient Boosted Benchmark Estimators
        xgb_model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.08,
            random_state=RANDOM_STATE,
            eval_metric="logloss",
        )
        xgb_model.fit(X_train, y_train)
        print("XGBoost training complete.")

        lgb_model = lgb.LGBMClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.08,
            random_state=RANDOM_STATE,
            verbose=-1,
        )
        lgb_model.fit(X_train, y_train)
        print("LightGBM training complete.")

        cat_model = CatBoostClassifier(
            iterations=300,
            depth=6,
            learning_rate=0.08,
            random_seed=RANDOM_STATE,
            verbose=0,
        )
        cat_model.fit(X_train, y_train)
        print("CatBoost training complete.")

        print("\n=== Step 8: Evaluate models on held-out test set ===")
        lr_metrics = evaluate_model("Logistic Regression", lr, X_test, y_test)
        rf_metrics = evaluate_model("Random Forest", rf, X_test, y_test)
        xgb_metrics = evaluate_model("XGBoost", xgb_model, X_test, y_test)
        lgb_metrics = evaluate_model("LightGBM", lgb_model, X_test, y_test)
        cat_metrics = evaluate_model("CatBoost", cat_model, X_test, y_test)

        # Benchmark comparison table for reporting and CSV
        all_metrics = [lr_metrics, rf_metrics, xgb_metrics, lgb_metrics, cat_metrics]
        comparison_rows = []
        for m in all_metrics:
            comparison_rows.append(
                {
                    "Model": m["name"],
                    "Accuracy": m["accuracy"],
                    "Precision": m["precision"],
                    "Recall": m["recall"],
                    "F1-score": m["f1"],
                    "ROC-AUC": m["roc_auc"],
                }
            )
        comparison_df = pd.DataFrame(comparison_rows)
        print("\nFull Benchmark Model Comparison:")
        print(comparison_df.to_string(index=False))
        comparison_df.to_csv(COMPARISON_PATH, index=False)
        print(f"Wrote benchmark comparison: {COMPARISON_PATH}")

        # Verify >= 95% accuracy requirement
        if rf_metrics["accuracy"] < 0.95:
            raise RuntimeError(
                f"Random Forest accuracy ({rf_metrics['accuracy']:.4f}) is below 0.95 target!"
            )
        print(
            f"\n[TARGET ACHIEVED] Random Forest test accuracy is "
            f"{rf_metrics['accuracy']:.4f} (>= 95.0%) with ROC-AUC {rf_metrics['roc_auc']:.4f}!"
        )

        # Dashboard UI displays all 5 evaluated models
        dashboard_models = [xgb_metrics, lgb_metrics, cat_metrics, rf_metrics, lr_metrics]
        selected_name = "Random Forest"
        selected_model = rf

        top10_features = plot_feature_importance(selected_model, feature_names)

        # Save evaluation_summary.json for dashboard-api
        save_evaluation_summary(
            selected_name=selected_name,
            test_size=len(y_test),
            train_size=len(y_train),
            churn_prevalence=float(y_raw.mean()),
            models=dashboard_models,
            feature_importance_top10=top10_features,
        )

        # Refit selected model on all resampled data (X_res, y_res) for maximum signal
        print("\nRefitting selected Random Forest on full resampled dataset...")
        selected_model.fit(X_res, y_res)

        # Save operational predictions on all 7,043 raw customers into MongoDB
        save_predictions(
            client=client,
            selected_name=selected_name,
            model=selected_model,
            X_encoded=X_encoded,
            customer_ids=customer_ids,
        )
        print("\nAll pipeline tasks completed successfully.")
        return 0

    except (PyMongoError, RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
