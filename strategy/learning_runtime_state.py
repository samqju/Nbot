"""Atomic persistence for unfinished learning lifecycles."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from copy import deepcopy
from pathlib import Path


class LearningRuntimeStateStore:
    VERSION = 1
    _SECTIONS = {
        "pending_simulations",
        "active_virtual_trades",
    }

    def __init__(self, path: str, system_log=None):
        self.path = Path(path)
        self.system_log = system_log
        self._lock = threading.RLock()
        self._document = self._load_or_default()

    def _default_document(self) -> dict:
        return {
            "version": self.VERSION,
            "updated_at_ms": int(time.time() * 1000),
            "pending_simulations": [],
            "active_virtual_trades": [],
        }

    def _load_or_default(self) -> dict:
        if not self.path.exists():
            return self._default_document()

        try:
            document = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"LEARNING_RUNTIME_STATE_LOAD_FAILED | {exc}"
            ) from exc

        if not isinstance(document, dict):
            raise RuntimeError("LEARNING_RUNTIME_STATE_NOT_OBJECT")
        if document.get("version") != self.VERSION:
            raise RuntimeError(
                "LEARNING_RUNTIME_STATE_VERSION_INVALID"
            )

        for section in self._SECTIONS:
            if not isinstance(document.get(section), list):
                raise RuntimeError(
                    "LEARNING_RUNTIME_STATE_SECTION_INVALID | "
                    f"section={section}"
                )

        return document

    def get_section(self, section: str) -> list:
        if section not in self._SECTIONS:
            raise ValueError(
                f"LEARNING_RUNTIME_STATE_SECTION_UNKNOWN | {section}"
            )
        with self._lock:
            return deepcopy(self._document[section])

    def replace_section(self, section: str, rows: list) -> None:
        self.replace_sections({section: rows})

    def replace_sections(self, sections: dict[str, list]) -> None:
        """Atomically replace one or more runtime sections in one disk write."""
        if not isinstance(sections, dict) or not sections:
            raise ValueError("LEARNING_RUNTIME_STATE_SECTIONS_INVALID")

        unknown = set(sections) - self._SECTIONS
        if unknown:
            section = sorted(unknown)[0]
            raise ValueError(
                f"LEARNING_RUNTIME_STATE_SECTION_UNKNOWN | {section}"
            )
        if any(not isinstance(rows, list) for rows in sections.values()):
            raise ValueError(
                "LEARNING_RUNTIME_STATE_ROWS_NOT_LIST"
            )

        with self._lock:
            for section, rows in sections.items():
                self._document[section] = deepcopy(rows)
            self._document["updated_at_ms"] = int(time.time() * 1000)
            self._write_atomic(self._document)

    def _write_atomic(self, document: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(
                    document,
                    handle,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
