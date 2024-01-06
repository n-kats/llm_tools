import logging
from datetime import datetime
from pathlib import Path

start = datetime.now().strftime("%Y%m%d%H%M%S")

default_logdir = Path("_logs")
default_loglevel = logging.INFO


def set_logger_default(logdir: Path = default_logdir, loglevel: int = default_loglevel):
    global default_logdir, default_loglevel
    default_logdir = logdir
    default_loglevel = loglevel


def get_logger(name, log_dir: Path = default_logdir, level=default_loglevel):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    log_path = log_dir / start / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
