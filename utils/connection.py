import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# =========================================================
# POSTGRES (validated lazily so `import` never crashes; call
# require_postgres_env() before connecting)
# =========================================================

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")


def require_postgres_env() -> dict[str, str]:
    """Validate Postgres env vars. Raises ValueError listing missing keys."""
    required = {
        "POSTGRES_HOST": POSTGRES_HOST,
        "POSTGRES_PORT": POSTGRES_PORT,
        "POSTGRES_DATABASE": POSTGRES_DATABASE,
        "POSTGRES_USERNAME": POSTGRES_USERNAME,
        "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return {k: str(v) for k, v in required.items()}


# Back-compat: validate eagerly only if explicitly requested via env.
if os.getenv("STRICT_ENV_CHECK", "").lower() in ("1", "true", "yes"):
    require_postgres_env()

# =========================================================
# MONGODB
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")


def get_mongo_db():
    _required_mongo = {"MONGO_URI": MONGO_URI, "MONGO_DB": MONGO_DB}

    _missing_mongo = [k for k, v in _required_mongo.items() if not v]

    if _missing_mongo:
        raise ValueError(
            f"Missing required environment variables: {', '.join(_missing_mongo)}"
        )

    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]
