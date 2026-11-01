"""
Query churn_db.predictions with MongoDB aggregations.

This script does not reuse in-memory training results. Every number comes
from the database.
"""

import os
import sys

from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Connection string: local MongoDB by default, Atlas via MONGODB_URI.
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

DATABASE_NAME = "churn_db"
PREDICTIONS_COLLECTION = "predictions"


def print_risk_counts(collection) -> None:
    pipeline = [
        {
            "$group": {
                "_id": "$risk_level",
                "count": {"$sum": 1},
            }
        }
    ]
    grouped = {row["_id"]: row["count"] for row in collection.aggregate(pipeline)}
    print("\n=== Customers by risk level ===")
    for level in ("High", "Medium", "Low"):
        count = grouped.get(level, 0)
        print(f"{level} risk: {count}")
    extra_levels = set(grouped) - {"High", "Medium", "Low"}
    for level in sorted(extra_levels, key=lambda value: str(value)):
        print(f"{level}: {grouped[level]}")
    if not grouped:
        print("No prediction documents were found.")


def print_top_customers(collection) -> None:
    print("\n=== Top 10 highest-risk customers ===")
    cursor = (
        collection.find(
            {},
            {
                "_id": 0,
                "customerID": 1,
                "churn_probability": 1,
                "risk_level": 1,
                "model_used": 1,
                "scored_at": 1,
            },
        )
        .sort("churn_probability", -1)
        .limit(10)
    )
    rows = list(cursor)
    if not rows:
        print("No prediction documents were found.")
        return
    print(
        f"{'customerID':<16} {'probability':>12} {'risk':<8} {'model':<22} scored_at"
    )
    for row in rows:
        print(
            f"{row.get('customerID', ''):<16} "
            f"{row.get('churn_probability', 0):>12.4f} "
            f"{row.get('risk_level', ''):<8} "
            f"{str(row.get('model_used', '')):<22} "
            f"{row.get('scored_at', '')}"
        )


def print_average_probability(collection) -> None:
    print("\n=== Average churn probability ===")
    pipeline = [
        {
            "$group": {
                "_id": None,
                "average_probability": {"$avg": "$churn_probability"},
                "count": {"$sum": 1},
            }
        }
    ]
    result = list(collection.aggregate(pipeline))
    if not result:
        print("No prediction documents were found.")
        return
    average = result[0]["average_probability"]
    count = result[0]["count"]
    print(f"Documents examined: {count}")
    print(f"Average churn probability: {average:.4f} ({average:.2%})")


def main() -> int:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        print("MongoDB connection successful.")
        collection = client[DATABASE_NAME][PREDICTIONS_COLLECTION]
        total = collection.count_documents({})
        print(f"Prediction documents in MongoDB: {total}")
        print_risk_counts(collection)
        print_top_customers(collection)
        print_average_probability(collection)
        print("Checkpoint passed: all three queries were read from MongoDB.")
        return 0
    except PyMongoError as exc:
        print(f"ERROR: MongoDB query failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
