import logging
import os
from datetime import datetime


def setup_logger(log_dir: str = "logs") -> tuple[logging.Logger, str]:
    """
    Configures the 'dot' logger for a single run.
    Returns (logger, log_file_path).

    File handler: DEBUG and above — full SQL, tracebacks, timing.
    Console handler: ERROR only — keeps terminal output clean.
    """
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"dot_{timestamp}.log")

    logger = logging.getLogger("dot")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if called more than once in a session
    if logger.handlers:
        logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_file
