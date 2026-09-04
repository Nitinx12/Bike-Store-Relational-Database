"""
src/database/jdbc_writer.py

Writes a Spark DataFrame to a Postgres staging table over JDBC. Isolated
from the merge step so staging writes and staging→target merges can be
retried, mocked, or swapped independently. Takes connection details as
plain arguments rather than importing pipeline config, so this module
has no dependency on src/pipeline/.
"""
from __future__ import annotations

from pyspark.sql import DataFrame


def write_to_staging(
    sdf: DataFrame,
    schema: str,
    staging: str,
    row_count: int,
    jdbc_url: str,
    user: str,
    password: str,
    log,
) -> None:
    """Overwrites (creates) the staging table with `sdf`'s rows via JDBC."""
    log.info("JDBC WRITE  : %d rows → %s.%s", row_count, schema, staging)
    (
        sdf.write
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", f'"{schema}"."{staging}"')
        .option("user", user)
        .option("password", password)
        .option("driver", "org.postgresql.Driver")
        .option("batchsize", "5000")
        .option("numPartitions", "4")
        .mode("overwrite")
        .save()
    )
    log.info("Staging write ✓")
