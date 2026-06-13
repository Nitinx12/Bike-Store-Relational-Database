# Run Book: mongo to postgres ETL

## Purpose

This run book explains how to operate the mongo to postgres incremental ETL script: how to run it, what each run mode does, required setup, environment variables, what each part of the code is responsible for, and how to troubleshoot common failures.

## Prerequisites

Before running the script, make sure the following are in place.

1. Project structure: the script expects to find a folder named utils containing connection.py, engine.py, and logger.py somewhere above it in the directory tree. It walks upward up to 8 parent directories looking for utils/connection.py to locate the project root.

2. PostgreSQL JDBC driver: a postgresql.jar file must exist at driver/postgresql.jar relative to the project root, or at the path specified by the JDBC_JAR_PATH environment variable. The script will refuse to start if this file is missing.

3. Python environment: pandas, pymongo, pyspark, and sqlalchemy must be installed and importable.

4. Connection details: MONGO_URI, MONGO_DB, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, POSTGRES_USERNAME, and POSTGRES_PASSWORD must be defined in utils/connection.py (or wherever that module sources them from, such as a .env file).

5. PostgreSQL connectivity: the script runs SELECT 1 against Postgres at startup and will fail immediately if this does not succeed.

## Environment Variables

| variable | default | purpose |
|---|---|---|
| ETL_SCHEMA | public | target Postgres schema where all tables are created and written |
| ETL_TS_COL | updated_at | name of the timestamp column used for incremental comparison and filtering |
| ETL_PK_SUFFIX | _id | suffix used to heuristically detect primary key columns |
| JDBC_JAR_PATH | project root / driver / postgresql.jar | path to the PostgreSQL JDBC driver jar used by Spark |
| PYSPARK_PYTHON | system python executable | python interpreter used by Spark workers |
| PYSPARK_DRIVER_PYTHON | system python executable | python interpreter used by the Spark driver |

## How to Run

All commands are run as a module from the project root.

### Incremental load, all collections

```
python -m scripts.mongo_to_postgres
```

This is the normal, scheduled run. The script auto discovers every collection in the configured MongoDB database, then for each one checks whether anything has changed since the last run (using the count and max timestamp comparison) and loads only the delta if so. Collections with no changes are skipped.

### Incremental load, specific collections

```
python -m scripts.mongo_to_postgres --collection staffs --collection orders
```

Restricts processing to the named collections only. Each named collection still goes through the same change detection and delta filtering as the full run. Useful for re running a single table after fixing an issue, without touching the rest.

### Full refresh, all collections

```
python -m scripts.mongo_to_postgres --full-refresh
```

Skips the change detection step entirely. For every collection, the entire MongoDB collection is read, the existing Postgres table is truncated (if it exists), and all data is reloaded fresh. Use this for initial backfills, after a schema change that the automatic column addition cannot handle, or to recover from data corruption.

### Full refresh, specific collections

```
python -m scripts.mongo_to_postgres --collection staffs --full-refresh
```

Combines the two: truncates and fully reloads only the named collection(s), leaving all other tables untouched. This is the recommended way to fix a single table that has gotten out of sync (for example, after the same-timestamp edge case described in incremental loading.md causes a record to be permanently missed).

Note: the script also accepts --full-load as a synonym for --full-refresh.

## What Happens During a Run, in Order

1. Logger is initialized and the run mode (incremental or full refresh) is logged along with the configured schema, timestamp column, and JDBC jar path.
2. If no collections were named on the command line, the script connects to MongoDB and lists all collection names to process.
3. A Spark session is created and a Postgres engine is created.
4. Postgres connectivity is verified with SELECT 1. If this fails, the run stops immediately.
5. Each collection is processed one at a time, in the order returned by MongoDB (or in the order given on the command line).
6. After all collections are processed, Spark is stopped and the Postgres engine is disposed.
7. A run summary is logged showing, per collection, whether it was loaded or skipped, and the mongo count, new row count, loaded row count, and failed row count. A grand total row is also logged.
8. If any collection had failed rows, the script exits with status code 1, so it can be detected by a scheduler or orchestration tool as a failed run.

## Python Script Feature Reference

This section explains what each function in mongo_to_postgres.py does.

### Project setup

**_find_project_root()**
Walks up to 8 parent directories from the script's location looking for a utils/connection.py file. This is how the script locates the project root regardless of where it is run from, so that imports of utils.connection, utils.engine, and utils.logger work correctly.

### Configuration and naming helpers

**_slugify(s)**
Converts any field name into a safe Postgres column name: lowercases it, strips special characters, replaces spaces and hyphens with underscores, and collapses repeated underscores. Used on every MongoDB field name before it becomes a Postgres column, and on collection names before they become table names.

**_staging_name(table, run_id)**
Builds the name of the temporary staging table for a given run, in the form table_staging_runid. The run id is a timestamp, so each run gets its own uniquely named staging table.

### Column detection

**detect_pk_col(columns, collection, log)**
Looks at the slugified column names from a sample of documents and tries to find a primary key column, in this priority order: a column matching the collection name plus _id, then any column ending in _id, then a column literally named id. Returns None if nothing matches, which triggers the row hash fallback for that collection.

**detect_ts_col(columns, log)**
Checks whether the configured timestamp column (default updated_at) exists among the slugified columns. Returns the column name if found, or None if not, which disables incremental filtering for that collection.

### Row hashing for collections without a primary key

**_add_row_hash(sdf, exclude_cols)**
Adds a column called _row_hash to the Spark DataFrame, computed as an MD5 hash of every data column concatenated together (excluding any columns passed in exclude_cols, such as loaded_at). This hash acts as a stand-in unique key so duplicate rows can be detected on re runs even without a natural primary key.

### Spark session

**get_spark(app_name)**
Builds and returns a SparkSession configured to run locally, with the PostgreSQL JDBC driver added to both the driver and executor classpaths, 2 gigabytes of driver memory, and a legacy time parser policy for compatibility with older date formats. Also sets the PYSPARK_PYTHON and PYSPARK_DRIVER_PYTHON environment variables so Spark uses the same Python interpreter that is running the script.

### MongoDB helpers

**_mongo_collection_stats(collection, ts_col_raw, log)**
Connects to MongoDB with PyMongo and returns the total document count for the collection, plus the maximum value of the timestamp column (computed with an aggregation pipeline) if a timestamp column was detected. Used to compare against Postgres in the change detection step.

**read_mongo_incremental(spark, collection, ts_col_raw, pg_max_ts, log)**
Reads documents from MongoDB. If a timestamp column exists and Postgres already has a maximum timestamp value, it filters the MongoDB query to only documents where the timestamp column is greater than that value, returning just the delta. Otherwise it reads the entire collection. Drops the MongoDB _id field, slugifies all column names, converts the result to a pandas DataFrame and then a Spark DataFrame, and preserves nulls correctly. Returns None if no documents match.

### PostgreSQL comparison helpers

**get_postgres_stats(engine, schema, table, ts_col, log)**
Checks whether the target table exists in Postgres, and if so returns its row count and, if the timestamp column exists in that table, its maximum value. Returns a dictionary with table_exists, count, and max_ts.

**needs_load(mongo_stats, pg_stats, ts_col, log)**
The core decision function. Returns True (meaning the collection should be loaded) if the target table does not exist yet, or if the MongoDB count is greater than the Postgres count, or if the timestamp column exists in both and MongoDB's maximum timestamp is newer than Postgres's. Otherwise returns False and the collection is skipped.

### PostgreSQL write helpers

**ensure_schema(conn, schema, log)**
Runs CREATE SCHEMA IF NOT EXISTS for the configured schema.

**ensure_target_table(conn, schema, table, columns, pk_col, log)**
Creates the target table if it does not exist, with every column typed as TEXT plus an auto incrementing _etl_id column, and a unique constraint on the primary key column (or on _row_hash if there is no primary key). Also performs schema evolution: compares the current MongoDB-derived column list against the existing Postgres columns and runs ALTER TABLE ADD COLUMN for any new fields, so new MongoDB fields automatically appear as new Postgres columns.

**merge_staging_to_target(conn, schema, table, staging, columns, pk_col, log)**
Runs the INSERT INTO target SELECT FROM staging statement. If a primary key column exists, this is an upsert using ON CONFLICT (pk) DO UPDATE, overwriting all columns with the staging values. If there is no primary key, it uses ON CONFLICT (_row_hash) DO NOTHING, so identical rows already present are silently skipped. Returns the row count of the staging table.

**drop_staging(conn, schema, staging, log)**
Runs DROP TABLE IF EXISTS for the staging table. Called after every merge attempt, including on failure, to avoid leaving temporary tables behind.

**truncate_table(conn, schema, table, log)**
Runs TRUNCATE TABLE with RESTART IDENTITY on the target table. Only called during a full refresh, and only if the table already existed.

### Core orchestration

**process_collection(collection, spark, engine, full_load)**
Runs the full pipeline for a single collection: peeks at sample documents to detect the primary key and timestamp columns, gets MongoDB and Postgres stats, decides whether to load (unless full_load is set), reads the incremental delta (or full collection on full refresh), adds the loaded_at audit column, deduplicates by primary key or row hash, ensures the schema and target table exist (including schema evolution), writes the delta to a staging table via JDBC, merges staging into the target table, drops the staging table, and returns a summary dictionary with row counts for that collection.

**main(collections, full_load)**
The top level entry point. Discovers collections if none were named, logs the run configuration, creates the Spark session and Postgres engine, verifies Postgres connectivity, loops over every collection calling process_collection, then stops Spark, disposes the engine, logs the final run summary table and totals, and exits with status 1 if any rows failed.

### Command line entry point

The bottom of the script parses sys.argv directly: --full-refresh or --full-load sets full_load to True, and one or more --collection name pairs build the list of collections to process. If no --collection arguments are given, all collections are auto discovered from MongoDB.

## Troubleshooting

**Script exits immediately with FileNotFoundError about postgresql.jar**
The JDBC driver is missing. Either place postgresql.jar at driver/postgresql.jar under the project root, or set the JDBC_JAR_PATH environment variable to point at an existing copy.

**Script raises RuntimeError about not finding the project root**
The script is being run from outside the project directory tree, or the utils folder with connection.py is missing or misplaced. Run the script from inside the project folder using the python -m scripts.mongo_to_postgres form.

**Run fails immediately at the Postgres connected check**
Postgres connection details in utils/connection.py are wrong, or the database is unreachable. Verify POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, POSTGRES_USERNAME, and POSTGRES_PASSWORD.

**A collection is always skipped even though you know data changed**
Check the timestamp column. If updated_at (or your configured ETL_TS_COL) is not being updated on writes in MongoDB, or if the change did not increase the count and the max timestamp did not move forward, needs_load will return False. Also check for the same-timestamp edge case: if a new row shares the exact same updated_at as the current Postgres maximum, it can be missed. Run a targeted full refresh for that collection to recover: python -m scripts.mongo_to_postgres --collection name --full-refresh.

**A collection fails during the JDBC staging write or the merge step**
Check the run summary for the failed row count. Common causes: a column's data does not fit as TEXT (unlikely since everything is TEXT), a constraint violation during merge (for example a no-PK collection where the unique constraint on _row_hash conflicts unexpectedly), or a Postgres permissions issue on CREATE TABLE / ALTER TABLE / DROP TABLE in the target schema. Staging tables are cleaned up automatically even on failure, so re running the same collection is safe.

**order_items or any collection with a composite key behaves unexpectedly**
The script's primary key detection only finds a single column. For order_items (composite key order_id, item_id, plus a generated total_value column), the auto detected primary key will be order_id only, which is incorrect for true uniqueness and will not match the existing composite primary key in Postgres. As noted in data catalog.md, this table needs a dedicated handling path (for example a synthetic combined key) before relying on this script for it. Until that is built, consider excluding order_items from automated runs and loading it separately.

**Want to add a new MongoDB field to an existing table**
Nothing to do manually. On the next run, ensure_target_table compares the incoming columns against the existing Postgres columns and runs ALTER TABLE ADD COLUMN automatically for any new field, added as TEXT.

**Need to reload everything from scratch (initial backfill or recovery)**
Run python -m scripts.mongo_to_postgres --full-refresh for all collections, or scope it to specific collections with --collection. This truncates existing tables (if present) and reloads the full MongoDB collection.