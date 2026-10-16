# logs to console and to logs/ file so runs are saved
import logging
import sys
from datetime import datetime
from pathlib import Path


# one logger per name, writes to console + file
def get_logger(name="etl"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # always show on console (stdout, so you see it)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # also save to logs/ folder at repo root
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(
        log_dir / f"{name}_{stamp}.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
