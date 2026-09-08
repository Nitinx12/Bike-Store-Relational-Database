"""
src/pipeline/spark_session.py

One SparkSession builder shared by every extract/transform step so JDBC
driver wiring, JVM options, and default parallelism live in exactly one
place.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

import os
import sys

from pyspark.sql import SparkSession

from src.pipeline.config import JDBC_JAR_PATH


def get_spark(app_name: str = "MongoToPublicETL") -> SparkSession:
    os.environ["PYSPARK_PYTHON"] = os.getenv("PYSPARK_PYTHON", sys.executable)
    os.environ["PYSPARK_DRIVER_PYTHON"] = os.getenv(
        "PYSPARK_DRIVER_PYTHON", sys.executable
    )

    master = os.getenv("SPARK_MASTER", "local[*]")
    driver_mem = os.getenv("SPARK_DRIVER_MEMORY", "2g")
    # Extra JVM modules (e.g. jdk.incubator.vector) — empty disables.
    extra_modules = os.getenv("SPARK_EXTRA_JAVA_MODULES", "jdk.incubator.vector")
    time_policy = os.getenv("SPARK_TIME_PARSER_POLICY", "LEGACY")

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.extraClassPath", JDBC_JAR_PATH)
        .config("spark.executor.extraClassPath", JDBC_JAR_PATH)
        .config("spark.driver.memory", driver_mem)
        .config("spark.sql.legacy.timeParserPolicy", time_policy)
        .config("spark.logConf", "false")
    )
    if extra_modules:
        java_opt = f"--add-modules {extra_modules}"
        builder = builder.config(
            "spark.driver.extraJavaOptions", java_opt
        ).config("spark.executor.extraJavaOptions", java_opt)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
    return spark
