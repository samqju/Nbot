from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time

LOG_FORMAT = "%(asctime)sZ %(levelname)s %(name)s %(message)s"


def configure_logging(
    *,
    role: str,
    profile: str,
    log_path: Path,
    level: int = logging.INFO,
    stderr: bool = True,
    component: str = "runtime",
) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    component = str(component or "runtime").strip().lower().replace(" ", "-")
    logger = logging.getLogger(f"nbot.v3.{role.lower()}.{profile}.{component}")
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime

    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if stderr:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def execution_log_paths(repo_root: Path, profile: str) -> dict[str, Path]:
    leaf = {"testnet-trade": "testnet", "live-paper": "paper", "live-trade": "real"}[profile]
    base = Path(repo_root) / "logs" / "execution" / leaf
    return {
        "execution": base / "execution.log",
        "trades": base / "trades.log",
        "runtime": base / "runtime.stdout.log",
    }


def observation_log_paths(repo_root: Path) -> dict[str, Path]:
    base = Path(repo_root) / "logs" / "observation" / "live"
    return {
        "collector": base / "collector.log",
        "control": base / "control.log",
        "research": base / "research.log",
    }
