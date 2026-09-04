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
    os.environ["PYSPARK_PYTHON"]        = os.getenv("PYSPARK_PYTHON",        sys.executable)
    os.environ["PYSPARK_DRIVER_PYTHON"] = os.getenv("PYSPARK_DRIVER_PYTHON", sys.executable)

    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.extraClassPath",     JDBC_JAR_PATH)
        .config("spark.executor.extraClassPath",   JDBC_JAR_PATH)
        .config("spark.driver.extraJavaOptions",   "--add-modules jdk.incubator.vector")
        .config("spark.executor.extraJavaOptions", "--add-modules jdk.incubator.vector")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .config("spark.driver.memory", "2g")
        .config("spark.logConf", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
