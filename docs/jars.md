# Driver Folder

This directory contains database driver files required by the project.

## Contents

### postgresql.jar
The `postgresql.jar` file is the official PostgreSQL JDBC Driver. Because this is a .jar (Java Archive) file residing in a Python project, it indicates that your Python code relies on a `Java Virtual Machine (JVM)` backend to establish the database connection.

* Common use cases for this setup include:

* Apache Spark (PySpark): When reading from or writing to a PostgreSQL database using Spark dataframes.

* JayDeBeApi: A Python module that uses JDBC drivers to connect to relational databases.

### Setup and Usage
When writing your execution scripts, you will need to point your application to the driver location.

Example for `PySpark`:
If you are initializing a Spark session, you must pass the path to the .jar file in your configuration:

```Python
from pyspark.sql import SparkSession
import os

# Define absolute path to the driver
driver_path = os.path.abspath("driver/postgresql.jar")

# Initialize Spark Session with the driver
spark = SparkSession.builder \
    .appName("PostgreSQL Connection") \
    .config("spark.jars", driver_path) \
    .getOrCreate()
```