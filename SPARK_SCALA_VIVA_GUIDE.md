# Comprehensive Spark & Scala Viva Defense Guide

This guide contains complete technical answers and viva-oriented explanations for the Apache Spark, PySpark, Spark MLlib, and Scala architecture implemented in the Telco Churn Analytics platform.

---

## 1. Spark Architecture & Core Concepts

### Q1: What are the fundamental components of an Apache Spark cluster?
- **Driver Program**: The process executing the `main()` method of your application. It creates the `SparkSession` / `SparkContext`, translates user code into a Directed Acyclic Graph (DAG) of stages and tasks, schedules tasks via `DAGScheduler` and `TaskScheduler`, and collects results.
- **Cluster Manager**: Allocates cluster resources. Supported managers include Standalone, Apache Mesos, Hadoop YARN, and Kubernetes. In our local setup, Spark runs in `local[*]` mode where the driver and executor threads share a single JVM.
- **Executors**: Worker processes spawned on cluster nodes that execute individual computational tasks, store cached RDD/DataFrame partitions in RAM/disk, and report task execution status and metrics back to the driver.
- **Job, Stage, Task Hierarchy**:
  - **Job**: Initiated whenever an *Action* (e.g., `.count()`, `.collect()`, `.write`) is invoked on a DataFrame or RDD.
  - **Stage**: A subset of a Job partitioned at *Shuffle boundaries* (wide dependencies like `groupBy`, `join`, `distinct`).
  - **Task**: The smallest individual unit of execution, dispatched by the driver to an executor core for a specific data partition.

---

### Q2: What is Lazy Evaluation, and why is it beneficial?
In Apache Spark, operations are divided into:
1. **Transformations** (e.g., `select`, `filter`, `withColumn`, `groupBy`, `sampleBy`): These do not immediately compute results; instead, they append an operation to the logical execution plan / lineage graph.
2. **Actions** (e.g., `count`, `collect`, `show`, `write.parquet`, `save`): These trigger the compilation of the logical plan into a physical DAG and execute the stages across executor threads.

**Benefits**:
- **Global Optimization**: Spark's Catalyst engine inspects the entire query DAG before executing any byte of computation, enabling optimizations like predicate pushdown (filtering at the storage reader) and projection pruning (reading only requested columns).
- **Avoiding Redundant I/O**: Intermediary datasets that are filtered or aggregated do not need to be materialized to RAM or disk.

---

### Q3: What is the difference between Narrow and Wide Dependencies?
- **Narrow Dependency** (`map`, `filter`, `withColumn`): Each partition of the parent RDD/DataFrame is consumed by at most one child partition. Execution can occur in parallel within the same executor thread without cross-network data transfer (pipelining).
- **Wide Dependency** (`groupByKey`, `groupBy`, `join`, `distinct`): Multiple child partitions require data from multiple parent partitions. This requires a **Shuffle** phase where data is partitioned by hash key, written to shuffle disk files, and transferred over the network to destination executors.

---

## 2. Abstractions: RDD vs. DataFrame vs. Dataset

| Dimension | Resilient Distributed Dataset (RDD) | DataFrame | Dataset (`Dataset[T]`) |
|---|---|---|---|
| **Type Safety** | Compile-time typed in Scala (`RDD[T]`) | Untyped (`DataFrame = Dataset[Row]`) | Strongly typed at compile-time (`Dataset[Customer]`) |
| **Optimization** | None (opaque JVM objects, garbage collection overhead) | Full Catalyst optimization & Tungsten binary format | Full Catalyst optimization + typed lambdas |
| **Serialization** | Java / Kryo serialization (CPU intensive) | Tungsten off-heap binary format (`UnsafeRow`) | Specialized Spark Encoders (fast bytecode generation) |
| **API Style** | Low-level functional (`rdd.map(x => (x, 1))`) | Declarative SQL-like (`df.filter($"tenure" > 24)`) | Object-oriented functional (`ds.filter(_.tenure > 24)`) |
| **Primary Language** | Scala / Java / Python | Python / Scala / Java / R | Scala / Java only (requires JVM compile-time types) |

---

## 3. Catalyst Optimizer & Project Tungsten

### Q4: Walk through the stages of Catalyst query optimization.
When a DataFrame query or Spark SQL string is submitted:
1. **Unresolved Logical Plan**: Validates syntax; column references and table names remain unresolved.
2. **Analyzed Logical Plan**: The Catalog resolves column names, data types, and view identifiers against schemas.
3. **Optimized Logical Plan**: Applies deterministic rule-based transformations:
   - *Predicate Pushdown*: Pushes `WHERE` conditions to the file format level (e.g., Parquet row group filtering).
   - *Projection Pruning*: Drops unused columns from disk reads.
   - *Constant Folding*: Computes constant expressions (`1 + 1` $\to$ `2`) at compile time.
4. **Physical Planning**: Generates candidate physical execution plans and uses Cost-Based Optimization (CBO) to select the optimal plan (e.g., deciding between `BroadcastHashJoin` vs `SortMergeJoin`).
5. **Code Generation (Tungsten)**: Compiles the selected physical plan into native Java bytecode via *Whole-Stage Code Generation*, removing virtual function calls and utilizing CPU registers.

---

## 4. Spark MLlib & Machine Learning Pipelines

### Q5: Why must preprocessing stages be placed INSIDE the ML Pipeline?
Placing `StringIndexer`, `OneHotEncoder`, `VectorAssembler`, and `StandardScaler` inside the `Pipeline` object ensures:
1. **Zero Data Leakage**: Transformers and estimators fit their parameters (e.g., mean and standard deviation for `StandardScaler`, category dictionaries for `StringIndexer`) strictly on the training partitions (`train`).
2. **Deterministic Evaluation**: When evaluating on the held-out test partition (`test`), the `PipelineModel` applies the exact pre-calculated means and variances without recomputing them on test data.
3. **Production Portability**: The entire fitted pipeline is exported as a unified artifact (`models/spark_rf_pipeline`) that can score raw inference inputs with no external preprocessing scripts.

---

### Q6: Why was Naive Bayes excluded from the classification benchmark?
Naive Bayes assumes feature probabilities follow multinomial or Bernoulli distributions and strictly requires non-negative feature vectors ($x_i \ge 0$). Because our pipeline incorporates zero-mean standardized numerical features (`StandardScaler(withMean=True, withStd=True)`), features contain negative z-scores, violating the mathematical preconditions of Naive Bayes.

---

### Q7: Why is LinearSVC unsuitable for probabilistic churn risk scoring?
`LinearSVC` optimizes the hinge loss to find the maximum-margin hyperplane:
$$\min_{\mathbf{w}, b} \frac{1}{2}\|\mathbf{w}\|^2 + C \sum_{i=1}^n \max\left(0, 1 - y_i(\mathbf{w}^T \mathbf{x}_i + b)\right)$$
The model outputs a raw geometric distance (margin), not a calibrated posterior class probability $P(Y=1 \mid X)$. Random Forest, Logistic Regression, and GBT generate calibrated probabilities in $[0, 1]$, making Random Forest the appropriate scoring model for tiered customer risk assignment.

---

## 5. Storage & Data Architecture: Parquet Marts

### Q8: What makes Parquet superior to CSV/JSON for analytical queries?
- **Columnar Layout**: Data is organized by column rather than row. Queries that compute aggregations over `MonthlyCharges` read only the bytes associated with that column, bypassing other columns completely.
- **Snappy Compression**: High-throughput compression with low decompression latency.
- **Metadata & Statistics**: Every Parquet file contains footer metadata storing `min` and `max` values for every column chunk. Queries like `WHERE tenure > 48` can skip entire row groups without reading or decompressing data.
- **Dictionary Encoding**: Compact integer representation for low-cardinality categorical fields (e.g., `Contract`, `InternetService`).

---

## 6. Scala Companion & Functional Programming Concepts

### Q9: Explain the functional programming constructs implemented in `CollectionsDemo.scala`.
1. **Partition**: Splits a collection into a pair of lists based on a predicate in a single traversal:
   `val (churned, retained) = customers.partition(_.Churn == "Yes")`
2. **Closures**: Functions that capture lexical variables from their enclosing scope:
   `val isHighValue: Customer => Boolean = c => c.MonthlyCharges >= threshold`
3. **foldLeft**: Tail-recursive accumulator processing elements sequentially:
   `val total = customers.foldLeft(0.0)((acc, c) => acc + c.TotalCharges)`
4. **Pattern Matching**: Type-safe structural matching over multi-variable tuples:
   ```scala
   (contract, internet) match {
     case ("Month-to-month", "Fiber optic") => "Critical"
     case ("Month-to-month", _)             => "Elevated"
     case ("One year", _)                   => "Watch"
     case ("Two year", _)                   => "Stable"
   }
   ```
5. **Lazy Streams**: Infinite data generator `Stream.from(1).map(...)` that evaluates elements only when demanded by downstream consumers (`take(10)`), demonstrating how functional streams handle unbounded real-time event feeds without memory exhaustion.

