from __future__ import annotations

import collections
import logging
import time
from pathlib import Path


class RingBufferHandler(logging.Handler):
    def __init__(self, capacity: int = 1000):
        super().__init__()
        self._records: collections.deque[str] = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(self.format(record))

    def tail(self, n: int = 200) -> list[str]:
        return list(self._records)[-max(0, n) :]


def configure_logging(log_dir: str | None = None, logger_name: str = "movieripper") -> tuple[logging.Logger, RingBufferHandler, Path | None]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logger.addHandler(stream_handler)

    file_path: Path | None = None
    if log_dir:
        log_root = Path(log_dir)
        log_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        file_path = log_root / f"movieripper_{stamp}.log"
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)

    ring_handler = RingBufferHandler()
    ring_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logger.addHandler(ring_handler)

    return logger, ring_handler, file_path
