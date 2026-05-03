# src/aggregator/logger.py
import logging
import sys
from pathlib import Path


def setup_logger():
    """
    Set up and return the "zurich_aggregator" logger configured with both console and file handlers.
    
    Clears any existing handlers to prevent duplicate output. Adds a console StreamHandler that emits INFO-level messages to stdout with a timestamp/level/name/message format, and a UTF-8 FileHandler that emits DEBUG-level messages to results/scraper.log with function name and line number. Ensures the "results" directory exists before creating the file handler.
    
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
