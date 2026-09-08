from __future__ import annotations

import logging

from pymongo import MongoClient
from pymongo.database import Database
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

from utils.connection import (
    MONGO_DB,
    MONGO_URI,
    POSTGRES_DATABASE,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USERNAME,
    require_postgres_env,
)

logger = logging.getLogger("engines")


# =========================================================
# POSTGRES
# =========================================================


def postgres_engine() -> Engine:
    require_postgres_env()
    try:
        connection_url = (
            "postgresql+psycopg2://"
            f"{POSTGRES_USERNAME}:"
            f"{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:"
            f"{POSTGRES_PORT}/"
            f"{POSTGRES_DATABASE}"
        )

        engine = create_engine(
            connection_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

        logger.info("Postgres engine created → %s/%s", POSTGRES_HOST, POSTGRES_DATABASE)
        return engine

    except SQLAlchemyError as e:
        logger.error("Postgres engine failed: %s", e)
        raise


# =========================================================
# MONGODB
# =========================================================


def mongo_client() -> Database:
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        logger.info("MongoDB connected → %s", MONGO_DB)
        return db

    except Exception as e:
        logger.error("MongoDB connection failed: %s", e)
        raise
