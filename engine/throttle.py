# ==========================================================
# LOG THROTTLE
# ==========================================================
# Owns:
# - Repeated log suppression
# - Time-window based emission
# - Automatic stale-key cleanup
# ==========================================================

import time


class LogThrottle:

    def __init__(self, logger):
        self.logger = logger
        self._store = {}

        self._THROTTLE_SECONDS = 10
        self._MAX_KEYS = 500

    # --------------------------------------------------
    # Public
    # --------------------------------------------------

    def log(self, *, key: str, level: str, message: str):

        now = time.time()
        entry = self._store.get(key)

        # First occurrence
        if entry is None:
            self._store[key] = {
                "last_emit": now,
                "suppressed": 0,
                "last_message": message,
            }
            self._emit(level, message)
            return

        elapsed = now - entry["last_emit"]

        # Within throttle window
        if elapsed < self._THROTTLE_SECONDS:
            entry["suppressed"] += 1
            entry["last_message"] = message
            return

        # Window expired
        if entry["suppressed"] > 0:
            summary = (
                f"{entry['last_message']} "
                f"(suppressed {entry['suppressed']} repeats)"
            )
            self._emit(level, summary)
        else:
            self._emit(level, message)

        entry["last_emit"] = now
        entry["suppressed"] = 0
        entry["last_message"] = message

        if len(self._store) > self._MAX_KEYS:
            self._cleanup(now)

    # --------------------------------------------------
    # Internal
    # --------------------------------------------------

    def _emit(self, level: str, message: str):

        if level == "critical":
            self.logger.critical(message)
        elif level == "info":
            self.logger.info(message)
        else:
            self.logger.info(message)

    def _cleanup(self, now: float):

        keys_to_delete = []

        for k, v in self._store.items():
            if now - v["last_emit"] > self._THROTTLE_SECONDS * 5:
                keys_to_delete.append(k)

        for k in keys_to_delete:
            del self._store[k]
