# builds the db connections used by the etl
from pymongo import MongoClient
from sqlalchemy import create_engine

from src.utils.connection import (
    MONGO_DB_NAME,
    MONGO_URI,
    postgres_url,
    require_mongo_env,
    require_pg_env,
)


# postgres engine for normal reads and writes
def postgres_engine():
    require_pg_env()
    return create_engine(postgres_url(), pool_pre_ping=True)


# mongo db handle for pulling source collections
def mongo_db():
    require_mongo_env()
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]
