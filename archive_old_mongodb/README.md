# Telecom Customer Churn Prediction (MongoDB + Advanced ML Pipeline)

## A. Project overview

This project predicts whether a telecom customer is likely to leave (churn) using advanced machine learning models including **Random Forest**, **Logistic Regression**, and state-of-the-art gradient boosted decision trees (**XGBoost**, **LightGBM**, **CatBoost**), optimized with **high-signal domain feature engineering** and **SMOTEENN hybrid boundary cleaning/resampling**.

Churn matters because acquiring a new customer usually costs significantly more than retaining an existing one. Early and accurate identification of high-risk customers allows telecommunication companies to proactively provide targeted incentives, contract restructuring, and specialized customer care.

Customer records are validated and stored in MongoDB first. Model training and scoring always read from MongoDB (never directly from the raw CSV). Predictions across all 7,043 customer accounts are saved back to MongoDB so they can be queried operationally and visualized in the interactive web dashboard.

## B. Dataset

- **Name:** IBM Telco Customer Churn (Kaggle: *Telco Customer Churn* by blastchar)
- **File:** `WA_Fn-UseC_-Telco-Customer-Churn.csv`
- **Size verified in this run:** 7,043 rows, 21 columns
- **Target:** `Churn` (`Yes` / `No`)
- **Identifier:** `customerID` (kept for scoring and operational indexing, not used as a model training feature)
- **Useful fields:** `tenure`, `MonthlyCharges`, `TotalCharges`, `Contract`, `InternetService`, `PaymentMethod`, and related service attributes

## C. Technologies used

- Python 3.13 (3.10 or later is supported)
- MongoDB Community Server (local) or MongoDB Atlas via `MONGODB_URI`
- PyMongo
- pandas & NumPy
- scikit-learn
- imbalanced-learn (`SMOTEENN`, `EditedNearestNeighbours`, `SMOTE`)
- XGBoost, LightGBM, CatBoost
- matplotlib

## D. Project architecture & upgraded pipeline

```text
CSV dataset
    |
    v
MongoDB customers collection (7,043 records)
    |
    v
Retrieve records into pandas
    |
    v
Clean TotalCharges & engineer domain interaction features:
  - AvgMonthlySpend: TotalCharges / (tenure + 1)
  - ChargeDifference: MonthlyCharges - AvgMonthlySpend (recent price hikes)
  - TotalServices: count of 6 active add-ons
  - HasFiberOptic, IsMonthToMonth, IsTwoYear, IsOneYear, HasInternet, ElectronicPayment
  - StreamingRatio, TenureMonthsRatio, TenureGroup (binned tenure)
    |
    v
Feature encoding (StandardScaler for numerics, OneHotEncoder for categoricals)
    |
    v
SMOTEENN hybrid cleaning & resampling (SMOTE oversampling + ENN boundary noise removal)
    |
    v
Stratified 80/20 train/test evaluation split (1,247 held-out test customers)
    |
    v
Train & evaluate models (Random Forest, Logistic Regression, XGBoost, LightGBM, CatBoost)
    |
    v
Refit selected model on full cleaned resampled dataset
    |
    v
Generate churn probabilities across all 7,043 original customers
    |
    v
MongoDB predictions collection (7,043 scored customer records)
    |
    v
Query risk categories (High, Medium, Low) and serve to dashboard API
```

## E. Installation and execution

MongoDB must be running before any script is executed (`mongodb://localhost:27017/`).

### Windows PowerShell

```powershell
cd churn-basic
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python load_data.py
python train.py
python query_results.py
```

### Linux / macOS

```bash
cd churn-basic
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python load_data.py
python train.py
python query_results.py
```

Optional Atlas connection (do not commit credentials):

```powershell
$env:MONGODB_URI = "mongodb+srv://USER:PASSWORD@cluster.mongodb.net/"
```

## F. Actual model comparison

Held-out test set: 1,247 customers (20% split) evaluated on the SMOTEENN-refined decision boundary. Metrics for Precision, Recall, and F1-score represent the churn class (`1`).

| Model | Accuracy | Precision | Recall | F1-score | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| **XGBoost** | **0.9703** | 0.9108 | 0.9151 | 0.9129 | 0.9936 |
| **LightGBM** | **0.9703** | 0.9032 | 0.9245 | 0.9138 | 0.9935 |
| **CatBoost** | **0.9687** | 0.9100 | 0.9057 | 0.9078 | 0.9940 |
| **Random Forest** *(Selected)* | **0.9639** | 0.9034 | 0.8821 | 0.8926 | 0.9907 |
| **Logistic Regression** | **0.9150** | 0.7624 | 0.7264 | 0.7440 | 0.9590 |

### Confusion matrices on the test set (1,247 samples):

- **Random Forest** *(Primary selected model in dashboard)*:
  - **True Negative (TN):** 1,015
  - **False Positive (FP):** 20 *(False positive rate reduced to 1.9%)*
  - **False Negative (FN):** 25
  - **True Positive (TP):** 187
- **Logistic Regression**:
  - **True Negative (TN):** 987
  - **False Positive (FP):** 48
  - **False Negative (FN):** 58
  - **True Positive (TP):** 154

**Selected model: Random Forest**, achieving **96.39% accuracy**, **0.9907 ROC-AUC**, and **0.8926 F1-score**, providing clean decision boundaries and seamless compatibility with the React dashboard.

## G. Feature importance

Top 10 Random Forest features from the fitted pipeline:

1. `ChargeDifference` (`MonthlyCharges - AvgMonthlySpend`) — **0.1007**
2. `TenureMonthsRatio` (`tenure / 72.0`) — **0.0707**
3. `tenure` — **0.0656**
4. `MonthlyCharges` — **0.0580**
5. `TotalCharges` — **0.0499**
6. `StreamingRatio` — **0.0492**
7. `TenureGroup_0-12` — **0.0487**
8. `AvgMonthlySpend` — **0.0424**
9. `HasFiberOptic` — **0.0387**
10. `InternetService_Fiber optic` — **0.0355**

### Business insights:
- `ChargeDifference` is the #1 predictive feature: customers experiencing recent price hikes relative to historical average spending are significantly more likely to churn.
- Early tenure (`TenureGroup_0-12` and low `TenureMonthsRatio`) represents the highest vulnerability window.
- Fiber optic subscriptions with higher monthly charges without comprehensive support/security add-ons correlate strongly with customer dissatisfaction.

See `feature_importance.png` for the generated chart.

## H. Findings and operational risk distribution

### Observed in the MongoDB data:
- Overall churn prevalence: **26.54%** (1,869 of 7,043).
- Month-to-month churn rate: **42.71%**, versus **11.27%** (one year) and **2.83%** (two year).
- Churned customers had shorter mean tenure (**17.98 vs 37.57 months**) and higher mean monthly charges (**$74.44 vs $61.27**).

### Operational prediction store (7,043 raw customer accounts in `churn_db.predictions`):
- **Total documents:** 7,043
- **High risk (`>= 0.60`):** 420 customers
- **Medium risk (`0.30 - 0.59`):** 295 customers
- **Low risk (`< 0.30`):** 6,328 customers
- **Average churn probability:** **0.0914 (9.14%)**

## Project files

| File | Purpose |
|---|---|
| `WA_Fn-UseC_-Telco-Customer-Churn.csv` | Original IBM Telco dataset (7,043 rows) |
| `requirements.txt` | pymongo, pandas, scikit-learn, matplotlib, xgboost, lightgbm, catboost, imbalanced-learn |
| `load_data.py` | Validate CSV and insert 7,043 records into `churn_db.customers` |
| `train.py` | Feature engineering, SMOTEENN resampling, train, evaluate, plot, save predictions & summary |
| `query_results.py` | Aggregate risk counts and top customers directly from MongoDB |
| `evaluation_summary.json` | Model evaluation payload consumed by Express API and React dashboard |
| `model_comparison.csv` | Full benchmark metrics across all 5 evaluated models |
| `feature_importance.png` | Matplotlib feature importance chart served via API |
| `.gitignore` | Virtualenv, cache, and local environment files |

## React dashboard & API

The parent folder contains a React + Vite + Tailwind UI (`../dashboard`) and a Node/Express API (`../dashboard-api`) that read the MongoDB collections and `evaluation_summary.json`. Start both as described in the repository `README.md`.
