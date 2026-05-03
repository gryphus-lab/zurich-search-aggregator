# src/aggregator/logger.py
import logging
import sys
from pathlib import Path


def setup_logger():
    """
    Configure and return the module logger used by the scraper, including console and file handlers.
    
    Creates or reconfigures a logger named "zurich_aggregator". Existing handlers are cleared to prevent duplicate output. Attaches a console StreamHandler that writes INFO-level messages to stdout with a concise time/level/name/message format, and ensures a "results" directory exists before attaching a UTF-8 FileHandler that writes DEBUG-level logs to results/scraper.log with a detailed formatter including function name and line number.
    
    Returns:
        logging.Logger: The configured logger named "zurich_aggregator".
    """
    logger = logging.getLogger("zurich_aggregator")
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s", datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    log_dir = Path("results")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "scraper.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# Global logger
logger = setup_logger()
