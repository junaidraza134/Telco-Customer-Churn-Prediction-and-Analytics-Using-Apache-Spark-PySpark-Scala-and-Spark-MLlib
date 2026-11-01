"""
Data ingestion module for Telco Churn.
Reads the raw CSV using an explicit StructType, cleans and imputes TotalCharges,
adds engineered features, and writes curated Parquet, CSV, and JSON marts.
"""
from pathlib import Path
import sys
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
)
from pyspark.sql import functions as F

from config import (
    RAW_CSV,
    CUSTOMERS_PARQUET,
    CUSTOMERS_CSV_DIR,
    API_CUSTOMERS_JSON,
    EXPECTED_ROWS,
    ensure_dirs,
    add_engineered_features,
)
from spark_session import get_spark


def get_raw_schema() -> StructType:
    """Explicit StructType for all 21 raw columns (no schema inference)."""
    return StructType(
        [
            StructField("customerID", StringType(), False),
            StructField("gender", StringType(), True),
            StructField("SeniorCitizen", IntegerType(), True),
            StructField("Partner", StringType(), True),
            StructField("Dependents", StringType(), True),
            StructField("tenure", IntegerType(), True),
            StructField("PhoneService", StringType(), True),
            StructField("MultipleLines", StringType(), True),
            StructField("InternetService", StringType(), True),
            StructField("OnlineSecurity", StringType(), True),
            StructField("OnlineBackup", StringType(), True),
            StructField("DeviceProtection", StringType(), True),
            StructField("TechSupport", StringType(), True),
            StructField("StreamingTV", StringType(), True),
            StructField("StreamingMovies", StringType(), True),
            StructField("Contract", StringType(), True),
            StructField("PaperlessBilling", StringType(), True),
            StructField("PaymentMethod", StringType(), True),
            StructField("MonthlyCharges", DoubleType(), True),
            StructField("TotalCharges", StringType(), True),  # String to handle blanks
            StructField("Churn", StringType(), True),
        ]
    )


def ingest_and_curate():
    """Run data ingestion, validation, imputation, and export."""
    ensure_dirs()
    spark = get_spark("TelcoChurnIngestion")

    print(f"Reading raw CSV from {RAW_CSV} with explicit schema...")
    raw_schema = get_raw_schema()
    df = (
        spark.read.option("header", "true")
        .schema(raw_schema)
        .csv(str(RAW_CSV))
    )

    # Validation: row count and column count
    row_count = df.count()
    col_count = len(df.columns)
    print(f"Ingested {row_count} rows, {col_count} columns.")
    assert (
        row_count == EXPECTED_ROWS
    ), f"Expected {EXPECTED_ROWS} rows, got {row_count}"
    assert col_count == 21, f"Expected 21 columns, got {col_count}"

    # Validation: zero duplicate customerIDs
    distinct_customers = df.select("customerID").distinct().count()
    print(f"Distinct customerIDs: {distinct_customers}")
    assert (
        distinct_customers == EXPECTED_ROWS
    ), f"Duplicate customerIDs found: {EXPECTED_ROWS - distinct_customers}"

    # Check blank/whitespace TotalCharges rows
    blank_charges_df = df.filter(
        (F.col("TotalCharges").isNull()) | (F.trim(F.col("TotalCharges")) == "")
    )
    blank_count = blank_charges_df.count()
    print(f"Rows with blank/whitespace TotalCharges: {blank_count}")
    assert blank_count == 11, f"Expected 11 blank TotalCharges rows, got {blank_count}"

    # Impute blank TotalCharges: MonthlyCharges * tenure
    # When blank/null: cast MonthlyCharges * tenure to Double; else cast TotalCharges string to Double
    df_imputed = df.withColumn(
        "TotalCharges",
        F.when(
            (F.col("TotalCharges").isNull()) | (F.trim(F.col("TotalCharges")) == ""),
            F.round(F.col("MonthlyCharges") * F.col("tenure"), 2),
        ).otherwise(F.col("TotalCharges").cast(DoubleType())),
    )

    # Add engineered features
    df_curated = add_engineered_features(df_imputed)

    # Validation on curated dataset
    curated_rows = df_curated.count()
    curated_cols = len(df_curated.columns)
    print(f"Curated DataFrame: {curated_rows} rows, {curated_cols} columns.")
    assert (
        curated_rows == EXPECTED_ROWS
    ), f"Expected {EXPECTED_ROWS} rows after curation, got {curated_rows}"
    assert curated_cols == 27, f"Expected 27 columns after curation, got {curated_cols}"

    print("Curated schema:")
    df_curated.printSchema()

    # Write Parquet mart
    print(f"Writing Parquet mart to {CUSTOMERS_PARQUET}...")
    df_curated.write.mode("overwrite").parquet(str(CUSTOMERS_PARQUET))

    # Write single-file CSV mart (coalesce(1))
    print(f"Writing CSV mart to {CUSTOMERS_CSV_DIR}...")
    df_curated.coalesce(1).write.mode("overwrite").option("header", "true").csv(
        str(CUSTOMERS_CSV_DIR)
    )

    # Write JSON export for API
    print(f"Writing JSON export to {API_CUSTOMERS_JSON}...")
    pdf = df_curated.toPandas()
    pdf.to_json(str(API_CUSTOMERS_JSON), orient="records", indent=2)

    print("Ingestion complete. All assertions passed and marts generated.")
    spark.stop()


if __name__ == "__main__":
    ingest_and_curate()
