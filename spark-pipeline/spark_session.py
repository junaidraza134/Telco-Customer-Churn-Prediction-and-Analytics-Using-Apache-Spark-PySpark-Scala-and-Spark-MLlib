"""
SparkSession factory configured for standalone local mode.
Includes Windows-specific Hadoop/winutils setup and Java 21 compatibility flags.
"""
import os
import sys
from pathlib import Path
import pyspark
from pyspark.sql import SparkSession


def configure_environment():
    """Configure system environment variables for Windows and PySpark."""
    # Java 21 setup
    jdk_path = Path(r"C:\Program Files\Java\jdk-21.0.10")
    if jdk_path.exists():
        os.environ["JAVA_HOME"] = str(jdk_path)
        jdk_bin = str(jdk_path / "bin")
        if jdk_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{jdk_bin};{os.environ.get('PATH', '')}"

    # Hadoop winutils setup
    hadoop_home = Path(r"C:\hadoop")
    if hadoop_home.exists():
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        hadoop_bin = str(hadoop_home / "bin")
        if hadoop_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{hadoop_bin};{os.environ.get('PATH', '')}"

    # Spark home and python executable
    spark_home = os.path.dirname(pyspark.__file__)
    os.environ["SPARK_HOME"] = spark_home
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


def get_spark(app_name: str = "TelcoChurnAnalytics") -> SparkSession:
    """
    Create or retrieve a SparkSession configured per project specifications:
    - master("local[*]")
    - spark.driver.memory=4g
    - spark.sql.shuffle.partitions=8
    - Adaptive Query Execution enabled
    - Log level set to ERROR
    """
    configure_environment()

    # Java 21 module access options
    java_options = (
        "--add-opens=java.base/java.lang=ALL-UNNAMED "
        "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED "
        "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED "
        "--add-opens=java.base/java.io=ALL-UNNAMED "
        "--add-opens=java.base/java.net=ALL-UNNAMED "
        "--add-opens=java.base/java.nio=ALL-UNNAMED "
        "--add-opens=java.base/java.util=ALL-UNNAMED "
        "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED "
        "--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED "
        "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
        "--add-opens=java.base/sun.nio.cs=ALL-UNNAMED "
        "--add-opens=java.base/sun.security.action=ALL-UNNAMED "
        "--add-opens=java.base/sun.util.calendar=ALL-UNNAMED "
        "--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED"
    )

    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.driver.extraJavaOptions", java_options)
        .config("spark.executor.extraJavaOptions", java_options)
    )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


if __name__ == "__main__":
    spark = get_spark("TestSession")
    print(f"Spark version: {spark.version}")
    print(f"Master: {spark.conf.get('spark.master')}")
    print(f"Driver memory: {spark.conf.get('spark.driver.memory')}")
    print(f"Shuffle partitions: {spark.conf.get('spark.sql.shuffle.partitions')}")
    print(f"AQE enabled: {spark.conf.get('spark.sql.adaptive.enabled')}")
    spark.stop()
