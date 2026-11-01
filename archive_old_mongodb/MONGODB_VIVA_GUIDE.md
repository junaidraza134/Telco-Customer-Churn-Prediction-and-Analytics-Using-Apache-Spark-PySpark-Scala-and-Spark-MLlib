# MongoDB Project Viva Guide & Code Reference

**Project:** Telco Customer Churn Analytics
**Database:** `churn_db`
**Collections:** `customers` (7,043 documents), `predictions` (7,043 documents)

---

## 1. Quick Terminal Commands to Run in Front of Sir

Pehle terminal me virtual environment activate kar lo:

```powershell
cd "d:\Downloads D\Projects\Telco-Churn-Analytics\churn-basic"
.\.venv\Scripts\Activate.ps1
```

### Command A: Run Analytics & Predictions Query

```powershell
python query_results.py
```

**Expected Output:**

```text
MongoDB connection successful.
Prediction documents in MongoDB: 7043

=== Customers by risk level ===
High risk: 420
Medium risk: 295
Low risk: 6328

=== Top 10 highest-risk customers ===
customerID        probability risk     model                  scored_at
1285-OKIPP             1.0000 High     Random Forest          2026-10-18 21:17:30.823000
7206-GZCDC             1.0000 High     Random Forest          2026-10-18 21:17:30.823000
8375-DKEBR             1.0000 High     Random Forest          2026-10-18 21:17:30.823000
...

=== Average churn probability ===
Documents examined: 7043
Average churn probability: 0.0914 (9.14%)
Checkpoint passed: all three queries were read from MongoDB.
```

### Command B: Run Data Ingestion (Agar Sir bole data insert karke dikhao)

```powershell
python load_data.py
```

**Expected Output:**

```text
CSV validation passed.
MongoDB connection successful.
CSV row count: 7043
Number of inserted documents: 7043
Documents in MongoDB after insertion: 7043
Example customer document: {'customerID': '7590-VHVEG', ...}
Checkpoint passed: 7,043 customer records are stored in MongoDB.
```

### Command C: Direct MongoDB Shell (`mongosh`)

Terminal me type karo `mongosh`, fir ye queries ek-ek karke run karo:

```javascript
use churn_db

// 1. Total customers count
db.customers.countDocuments()
// Output: 7043

// 2. Risk level distribution (NOTE: $ sign zaroor lagana hai)
db.predictions.aggregate([
  { $group: { _id: "$risk_level", total: { $sum: 1 } } }
])
// Output: High: 420, Low: 6328, Medium: 295

// 3. Top 3 highest risk customer
db.predictions.find({}, { _id: 0, customerID: 1, churn_probability: 1, risk_level: 1 })
  .sort({ churn_probability: -1 })
  .limit(3)

// Shell se bahar aane ke liye
exit
```

---

## 2. Code Breakdown: Kahan aur Kaise MongoDB Use Hua Hai

---

### File 1: `churn-basic/load_data.py` (Data Ingestion & Bulk Insert)

#### Code Snippet:

```python
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "churn_db"
COLLECTION_NAME = "customers"

def import_customers(df):
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
  
    # 1. Connection ping
    client.admin.command("ping")
  
    collection = client[DATABASE_NAME][COLLECTION_NAME]
  
    # 2. Purane data ko drop karna
    collection.drop()
  
    # 3. Pandas DataFrame ko Dictionary list me convert karna
    records = df.to_dict("records")
  
    # 4. Bulk insert (High throughput)
    result = collection.insert_many(records)
  
    # 5. Count verification
    stored_count = collection.count_documents({})
  
    # 6. Sample fetch
    sample = collection.find_one({}, {"_id": 0})
  
    client.close()
```

#### Explanation:

* **`MongoClient`**: PyMongo ka client jo connection pool maintain karta hai.
* **`collection.drop()`**: Collection ko clean karke naye सिरे se fresh data load karta hai.
* **`insert_many(records)`**: Loop chala kar ek-ek document insert karne ke bajaye ek hi network request me saare 7,043 documents insert karta hai (Bulk write operation).
* **`{"_id": 0}` (Projection)**: Default `_id` field ko result se exclude kar deta hai taaki standard dictionary/JSON mile.

---

### File 2: `churn-basic/query_results.py` (Aggregation & Queries)

#### Code Snippet 1: Risk Level Grouping

```python
pipeline = [
    {
        "$group": {
            "_id": "$risk_level",      # Document ke field 'risk_level' ke hisaab se group
            "count": {"$sum": 1},      # Har document ke liye 1 add karo (counting)
        }
    }
]
grouped = {row["_id"]: row["count"] for row in collection.aggregate(pipeline)}
```

* **Kyun use kiya:** MongoDB ke database engine par grouping perform hoti hai, bina Python memory me saara data load kiye.

#### Code Snippet 2: Top 10 Customers (Sorting + Pagination + Projection)

```python
cursor = (
    collection.find(
        {},                            # Filter: saare documents
        {
            "_id": 0,                  # Projection: _id mat bhejo
            "customerID": 1,           # Sirf ye fields chahiye
            "churn_probability": 1,
            "risk_level": 1,
            "model_used": 1,
            "scored_at": 1,
        },
    )
    .sort("churn_probability", -1)     # -1 = Descending order (sabse high risk pehle)
    .limit(10)                         # Sirf top 10 documents
)
```

* **Kyun use kiya:** Fast response time aur optimized network payload.

#### Code Snippet 3: Average Churn Probability

```python
pipeline = [
    {
        "$group": {
            "_id": None,                                  # Pure collection ka ek hi group
            "average_probability": {"$avg": "$churn_probability"}, # Mean calculate
            "count": {"$sum": 1},
        }
    }
]
result = list(collection.aggregate(pipeline))
```

* **Kyun use kiya:** `$avg` accumulator MongoDB me naturally floats calculate karta hai.

---

### File 3: `churn-basic/train.py` (ML Pipeline Integration)

#### 1. Data Fetching:

```python
# Raw customer data MongoDB se fetch karna:
collection = client["churn_db"]["customers"]
records = list(collection.find({}, {"_id": 0}))
df = pd.DataFrame(records)
```

* ML model direct CSV se nahi, hamesha live MongoDB database se train hota hai.

#### 2. Predictions Store Back to MongoDB:

```python
documents = []
for customer_id, probability in zip(customer_ids, probabilities):
    documents.append({
        "customerID": customer_id,
        "churn_probability": round(float(probability), 4),
        "risk_level": "High" if probability >= 0.60 else ("Medium" if probability >= 0.30 else "Low"),
        "model_used": "Random Forest",
        "scored_at": datetime.now(timezone.utc)
    })

collection = client["churn_db"]["predictions"]
collection.drop()
collection.insert_many(documents)
```

* Model output probabilities ko operational database collection `predictions` me store kiya gaya hai taaki frontend dashboard aur marketing teams ise live access kar sakein.

---

### File 4: `dashboard-api/server.js` (Node.js MongoDB Driver & REST API)

#### 1. Database Indexing (Startup par create hoti hain):

```javascript
// server.js Lines 344-347
await db.collection("customers").createIndex({ customerID: 1 });
await db.collection("predictions").createIndex({ customerID: 1 });
await db.collection("predictions").createIndex({ churn_probability: -1 });
await db.collection("predictions").createIndex({ risk_level: 1 });
```

* **Kyun:** Bina index ke MongoDB ko pura collection scan karna padta hai (`COLLSCAN`). Indexing se search time `O(N)` se ghat kar `O(log N)` ho jata hai.

#### 2. Conditional Aggregation (Churn Rate by Contract):

```javascript
// server.js Lines 76-88
const contractRows = await customers.aggregate([
  {
    $group: {
      _id: "$Contract",
      total: { $sum: 1 },
      churned: {
        $sum: { $cond: [{ $eq: ["$Churn", "Yes"] }, 1, 0] }  // Conditional count
      }
    }
  }
]).toArray();
```

* `$cond` stage IF-ELSE logic implement karta hai: agar `Churn == "Yes"`, toh 1 count karo, varna 0.

#### 3. Data Type Casting with `$convert`:

```javascript
// server.js Lines 172-181
avgTotal: {
  $avg: {
    $convert: {
      input: "$TotalCharges",
      to: "double",
      onError: 0,
      onNull: 0
    }
  }
}
```

* Dataset me kuch `TotalCharges` string ya blank the. MongoDB ka `$convert` pipeline stage unhe safely double (float) me convert karke average nikalta hai.

#### 4. Filter, Regex Search & Pagination:

```javascript
// server.js Lines 151-208
const match = {};
if (contract) match.Contract = contract;
if (customerID) match.customerID = { $regex: customerID, $options: "i" }; // Case-insensitive search
if (tenureMin || tenureMax) {
  match.tenure = {};
  if (tenureMin) match.tenure.$gte = Number(tenureMin); // >=
  if (tenureMax) match.tenure.$lte = Number(tenureMax); // <=
}

const pageRows = await customers
  .find(match, { projection: { _id: 0 } })
  .sort({ customerID: 1 })
  .skip((page - 1) * pageSize)   // Pagination skip
  .limit(pageSize)               // Page limit
  .toArray();
```

---

## 3. Important Concepts to Remember

| Concept                                                                                                                                                      | Explanation                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **`"$field"` vs `"field"`** | `"$risk_level"` field ki value (High/Medium/Low) refer karta hai. `"risk_level"` sirf ek text string maanta hai. |                                                                                                                                                                                                        |
| **`{"_id": 0}`**                                                                                                                                     | MongoDB ka default 12-byte `ObjectId` hide karta hai taaki clean JSON payload mile.                                                                                                                  |
| **`insert_many()`**                                                                                                                                  | Bulk write operation jo thousands of documents ek sath insert karta hai.                                                                                                                               |
| **`skip()` & `limit()`**                                                                                                                           | Pagination ke liye use hota hai taaki ek baar me sirf 10-12 records load hon.                                                                                                                          |
| **`createIndex()`**                                                                                                                                  | Search query ko fast karne ke liye B-Tree data structure banata hai.                                                                                                                                   |
| **2 Collections Kyun?**                                                                                                                                | `customers` me static profile data hai. `predictions` me dynamic AI risk score hai. ML model retrain hone par sirf `predictions` drop & rebuild hota hai, original customer data safe rehta hai. |

---

## 4. Top Viva Questions & Answers

### Q1: MongoDB NoSQL kyun chuna, MySQL/SQL kyun nahi?

> **Answer:**
>
> 1. Customer profile me multiple services aur dynamic attributes hote hain jo JSON/BSON document model me naturally fit hote hain bina multiple table JOINs ke.
> 2. High write throughput: Model jab 7,000+ predictions ek sath score karta hai, MongoDB ka `insert_many` bulk write relational databases se kaafi fast perform karta hai.
> 3. Native Aggregation Framework real-time analytics direct database me calculate karta hai.

### Q2: Is project me kitni collections hain aur schema design kya hai?

> **Answer:**
> Do collections hain:
>
> 1. `customers`: Customer details, services, tenure, billing, actual churn status.
> 2. `predictions`: Model dwara nikala gaya churn probability, risk level (`High`, `Medium`, `Low`), model name aur timestamp.
>    Dono collections **`customerID`** field ke through reference kiye jaate hain.

### Q3: Aggregation Pipeline kya hoti hai aur kaunse stages use kiye?

> **Answer:**
> Aggregation pipeline documents par step-by-step data processing aur transformation karti hai. Humne use kiye:
>
> * `$match`: Filter karne ke liye (WHERE clause jaisa).
> * `$group`: Data group karke `$sum` aur `$avg` calculate karne ke liye.
> * `$cond`: Conditional calculation (churned count nikalne ke liye).
> * `$convert`: String `TotalCharges` ko double me cast karne ke liye.

### Q4: Indexes kyun banaye aur kaunse banaye?

> **Answer:**
> Full collection scan (`COLLSCAN`) avoid karne ke liye:
>
> * `customerID` par index banaya (fast single customer lookup).
> * `churn_probability` par index banaya (top high-risk sorting fast karne ke liye).
> * `risk_level` par index banaya (High/Medium/Low filtering ke liye).

### Q5: Project ke key metrics kya hain?

> * **Total Documents:** 7,043
> * **High Risk Accounts:** 420
> * **Medium Risk:** 295
> * **Low Risk:** 6,328
> * **Overall Average Churn Probability:** 9.14%
> * **Model Used:** Random Forest Classifier (96.39% test accuracy)
