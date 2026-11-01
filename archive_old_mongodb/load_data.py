"""
Validate the IBM Telco Customer Churn CSV and import it into MongoDB.

Database:  churn_db
Collection: customers

The CSV is validated first. The customers collection is dropped only after
validation succeeds so a bad file cannot wipe a previously loaded dataset.
"""

import os
import sys
from pathlib import Path

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Connection string: local MongoDB by default, Atlas via MONGODB_URI.
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

CSV_FILENAME = "WA_Fn-UseC_-Telco-Customer-Churn.csv"
EXPECTED_ROW_COUNT = 7043
DATABASE_NAME = "churn_db"
COLLECTION_NAME = "customers"

EXPECTED_COLUMNS = [
    "customerID",
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "tenure",
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
    "MonthlyCharges",
    "TotalCharges",
    "Churn",
]


def validate_csv(csv_path: Path) -> pd.DataFrame:
    """Load the CSV and raise ValueError if it is not the expected dataset."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}\n"
            "Download WA_Fn-UseC_-Telco-Customer-Churn.csv from Kaggle "
            "(search: Telco Customer Churn by blastchar) and place it next "
            "to this script. Do not substitute fake customer records."
        )

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        raise ValueError(f"Could not read the CSV file: {exc}") from exc

    errors = []

    if list(df.columns) != EXPECTED_COLUMNS:
        errors.append(
            "Column names do not match the expected IBM Telco dataset.\n"
            f"  Expected: {EXPECTED_COLUMNS}\n"
            f"  Found:    {list(df.columns)}"
        )

    if df.columns.isna().any() or any(str(col).strip() == "" for col in df.columns):
        errors.append("The CSV contains missing or blank column names.")

    if len(df) != EXPECTED_ROW_COUNT:
        errors.append(
            f"Expected {EXPECTED_ROW_COUNT} customer rows, found {len(df)}. "
            "Investigate the file instead of silently changing the data."
        )

    if "customerID" in df.columns:
        duplicate_ids = df["customerID"].duplicated().sum()
        if duplicate_ids:
            errors.append(f"Found {duplicate_ids} duplicate customerID values.")
        if df["customerID"].isna().any():
            errors.append("Found missing customerID values.")

    if "Churn" in df.columns:
        invalid_targets = set(df["Churn"].dropna().unique()) - {"Yes", "No"}
        if invalid_targets:
            errors.append(f"Invalid Churn values: {sorted(invalid_targets)}")
        if df["Churn"].isna().any():
            errors.append("Found missing Churn values.")

    if errors:
        raise ValueError("CSV validation failed:\n- " + "\n- ".join(errors))

    return df


def import_customers(df: pd.DataFrame) -> None:
    """Replace churn_db.customers with the validated records."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        print("MongoDB connection successful.")

        collection = client[DATABASE_NAME][COLLECTION_NAME]
        collection.drop()

        records = df.to_dict("records")
        result = collection.insert_many(records)
        inserted_count = len(result.inserted_ids)
        stored_count = collection.count_documents({})

        print(f"CSV row count: {len(df)}")
        print(f"Number of inserted documents: {inserted_count}")
        print(f"Documents in MongoDB after insertion: {stored_count}")

        sample = collection.find_one({}, {"_id": 0})
        print("Example customer document:")
        print(sample)

        if stored_count != EXPECTED_ROW_COUNT:
            raise RuntimeError(
                f"MongoDB contains {stored_count} documents, expected "
                f"{EXPECTED_ROW_COUNT}. Investigate before training."
            )
    except PyMongoError as exc:
        raise RuntimeError(f"MongoDB insertion failed: {exc}") from exc
    finally:
        client.close()


def main() -> int:
    csv_path = Path(__file__).resolve().parent / CSV_FILENAME
    print(f"Validating dataset: {csv_path}")

    try:
        df = validate_csv(csv_path)
        print("CSV validation passed.")
        import_customers(df)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Checkpoint passed: 7,043 customer records are stored in MongoDB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
