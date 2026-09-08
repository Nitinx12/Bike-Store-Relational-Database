import logging
import os
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _repo_log_dir(stage: str) -> Path:
    """Logs dir anchored at repo root (utils/connection.py marker)."""
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "utils" / "connection.py").exists():
            return current / "logs" / stage
        current = current.parent
    return Path.cwd() / "logs" / stage


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "app"


def get_logger(stage: str, name: str) -> logging.Logger:
    valid_stages = ["extraction", "transformation", "loading", "tests"]
    if stage not in valid_stages:
        raise ValueError(f"Invalid stage '{stage}'. Must be one of: {valid_stages}")

    safe_name = _sanitize(name)
    # Create logs/<stage>/ folder anchored at repo root
    log_dir = _repo_log_dir(stage)
    os.makedirs(log_dir, exist_ok=True)

    # Log file with second-granularity to avoid minute collisions
    run_time = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(str(log_dir), f"{safe_name}_{run_time}.log")

    # Unique logger key per stage+name
    logger_key = f"{stage}.{safe_name}"
    logger = logging.getLogger(logger_key)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid duplicate handlers (attach file handler once per process)
    if logger.handlers:
        return logger

    # formatter
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    # File Handler (DEBUG and above, rotated)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
