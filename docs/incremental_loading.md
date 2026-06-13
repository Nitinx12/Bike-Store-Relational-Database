# Incremental Loading Documentation: mongo to postgres ETL

## Overview

This script (mongo to postgres.py) is a PySpark based ETL pipeline that moves data from MongoDB collections into PostgreSQL tables. It is designed to run repeatedly on a schedule and only move new or changed data each time, instead of reloading everything. This is called incremental loading.

The script also supports a full refresh mode where everything is truncated and reloaded from scratch.

## Core Idea Behind Incremental Loading

Instead of relying on external config files, checkpoints, or saved state, the script uses PostgreSQL itself as the source of truth for "what has already been loaded". On every run it compares MongoDB to PostgreSQL directly:

1. Count of documents in MongoDB versus count of rows in PostgreSQL
2. Maximum value of a timestamp column (default updated at) in MongoDB versus PostgreSQL

If both of these match, the script assumes nothing has changed and skips that collection entirely. If they differ, it pulls only the rows that are newer than what PostgreSQL already has.

## Step by Step Flow

### Step 1: Peek at the collection

For each collection, the script fetches a small sample (10 documents) from MongoDB to discover the field names. These names are then normalized (slugified) into safe PostgreSQL column names, for example removing spaces, special characters, and converting to lowercase with underscores replaced consistently.

From this sample, two important columns are auto detected.

#### Primary key detection (pk col)

The script looks for a primary key column using this priority order:

1. A column that matches the collection name plus "id" suffix, for example a collection named artist would look for artist id
2. The first column ending in "id" if no exact match is found
3. A column literally named id as a fallback

If none of these exist, the collection is treated as having no primary key, and a row hash strategy is used instead (explained later).

#### Timestamp column detection (ts col)

The script checks whether a column named updated at exists (this name is configurable through an environment variable). This column is critical for incremental filtering. If it does not exist, the script logs a warning and falls back to a full snapshot comparison for that collection.

### Step 2: Get MongoDB statistics

Using PyMongo directly (not Spark), the script queries:

- Total document count in the collection
- Maximum value of the timestamp column, using an aggregation pipeline with a group and max operator

### Step 3: Get PostgreSQL statistics

Using SQLAlchemy, the script checks:

- Whether the target table already exists in the public schema
- Row count of the target table (zero if it does not exist)
- Whether the timestamp column exists in the PostgreSQL table, and if so, its maximum value

### Step 4: Decide whether to load (the needs load function)

This is the core decision point of incremental loading. The script loads data if any of the following are true:

1. The target table does not exist yet in PostgreSQL (first run for this collection)
2. MongoDB document count is greater than PostgreSQL row count (new records were inserted)
3. The timestamp column exists in both systems, and MongoDB's maximum timestamp is greater than PostgreSQL's maximum timestamp (existing records were updated, or new records with later timestamps exist)

If none of these conditions are true, the collection is skipped entirely and the script moves to the next collection. This avoids unnecessary Spark reads and JDBC writes when nothing has changed.

In full refresh mode, this comparison step is bypassed entirely.

### Step 5: Read the incremental delta from MongoDB

This is where the actual filtering happens.

- If running incrementally and the timestamp column exists, the script reads from MongoDB only the documents where the timestamp column is greater than the maximum timestamp already present in PostgreSQL. This is a direct MongoDB query filter, so the filtering happens at the source, not after loading everything.
- If running a full refresh, or if the timestamp column does not exist, or if PostgreSQL has no existing maximum timestamp (first run), the script reads the entire collection.

The data is read using PyMongo into a pandas DataFrame, column names are slugified, null and NaN values are preserved as proper SQL nulls rather than being converted to the string "None", and the result is converted into a Spark DataFrame.

If no documents are returned by this filtered query, the collection is marked as skipped.

### Step 6: Add audit and dedup columns

Before writing, the script adds a loaded at timestamp column to every row, recording when this ETL run happened.

It then performs deduplication:

- If a primary key column was detected, duplicate rows sharing the same primary key value are dropped (keeping one), and the count of removed duplicates is logged
- If no primary key column was detected, a row hash column is computed instead. This is an MD5 hash of all data columns concatenated together (excluding the loaded at column). This hash acts as a surrogate unique key for collections that have no natural identifier

### Step 7: Write to a staging table via JDBC

The script writes the filtered, deduplicated DataFrame to a temporary staging table named using the pattern: table name, staging, run id (a timestamp based unique identifier for this run).

This write uses the Spark JDBC connector in overwrite mode, meaning the staging table is recreated fresh each run with only the new delta rows. This staging table is schema specific and temporary, it always gets dropped at the end of processing.

### Step 8: Merge staging into the target table (the upsert logic)

This is where incremental data actually lands in the permanent table.

First, the script ensures the schema and target table exist:

- If the target table does not exist, it is created with all columns as TEXT type, plus an auto incrementing etl id column
- A unique constraint is added on either the primary key column, or on the row hash column if there is no primary key
- Schema evolution is applied automatically: if MongoDB documents contain new fields that are not yet columns in the PostgreSQL table, those columns are added on the fly using ALTER TABLE ADD COLUMN

Then the merge itself runs as an INSERT INTO target SELECT FROM staging statement, with conflict handling that differs based on whether a primary key exists:

- Collections with a primary key: ON CONFLICT (primary key) DO UPDATE, meaning if a row with that primary key already exists, all its columns get overwritten with the new values from staging. This is a true upsert, insert if new, update if existing.
- Collections without a primary key: ON CONFLICT (row hash) DO NOTHING, meaning if an identical row (by hash) already exists, it is silently skipped, preventing duplicate inserts on re runs.

If running in full refresh mode and the target table already existed, it is truncated (with identity reset) before the merge happens, so the merge effectively becomes a fresh full load.

### Step 9: Drop the staging table

Regardless of success or failure, the staging table is cleaned up using DROP TABLE IF EXISTS, so no leftover staging tables accumulate across runs.

## Why This Counts as True Incremental Loading

1. No external state files, checkpoints, or watermark tables are needed. PostgreSQL's own data is the watermark.
2. The skip check (Step 4) avoids touching Spark or JDBC entirely when there is nothing new, saving compute time.
3. The MongoDB query filter (Step 5) ensures only new or updated documents are pulled across the network and through Spark, not the entire collection, on every incremental run after the first.
4. The upsert logic (Step 8) ensures that even if a record was updated in MongoDB (same primary key, newer updated at value), the corresponding PostgreSQL row gets refreshed rather than duplicated.
5. Deduplication (row hash or primary key based) ensures re running the same incremental window does not create duplicate rows.

## First Run Behavior

On the very first run for any collection, the target table does not exist in PostgreSQL, so:

- needs load returns true immediately (table absent condition)
- pg max ts is none, so the MongoDB read has no filter and pulls the entire collection
- The target table is created fresh with schema evolution and the unique constraint
- All rows are inserted via the upsert path (insert branch, since nothing conflicts yet)

From the second run onward, the incremental filtering described above takes effect.

## Full Refresh Mode

When run with the full refresh flag (optionally scoped to specific collections):

- The needs load comparison (Step 4) is skipped, every targeted collection is processed regardless of whether anything changed
- The MongoDB read pulls the entire collection (pg max ts is forced to none)
- If the target table already exists, it is truncated before the merge, so old data is wiped and replaced entirely with the fresh full pull
- Schema evolution and table creation logic still run the same way

## Handling Collections Without a Timestamp Column

If the configured timestamp column (default updated at) is not present in a collection's documents:

- The timestamp based portion of the load decision and filtering is skipped
- The load decision then relies only on count comparison (MongoDB count greater than PostgreSQL count)
- The MongoDB read pulls the full collection every time it decides to load, since there is no timestamp to filter on
- Deduplication still works normally via primary key or row hash

## Handling Collections Without a Primary Key

If no suitable primary key like column is found:

- A row hash column is computed as an MD5 hash of all the data columns
- The target table's unique constraint is placed on this row hash column instead of a primary key
- The merge uses ON CONFLICT (row hash) DO NOTHING, so identical rows seen in a previous run are ignored rather than duplicated, but there is no update behavior since there is no stable identifier to update against

## Run Summary and Failure Handling

After processing all collections, the script logs a summary table showing, per collection: whether it was loaded or skipped, the MongoDB document count, the number of new delta rows found, the number of rows successfully merged, and the number of failed rows.

If any collection fails during the staging write or merge step, that collection's rows are counted as failed, staging tables are cleaned up on a best effort basis, and the script exits with a non zero status code at the end if any failures occurred across all collections, while still attempting to process every other collection in the run.