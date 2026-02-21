# ==========================================================
# STATE MODULE
# ==========================================================
# This module stores and retrieves bot state.
# It does NOT make trading decisions.
#
# Structural Guarantees:
# - State is validated before persistence
# - Open position must contain required fields
# - Daily accounting must remain monotonic
# - Balance cannot be negative
# ==========================================================

import json
import os
import copy

class StateManager:
    """
    StateManager persists bot memory safely.
    """

    # --------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------

    def __init__(self, filename="bot_state.json"):

        self.filename = filename

        self.state = {
            # ----------------------------
            # CORE ACCOUNT STATE
            # ----------------------------
            "balance": 0.0,

            # ----------------------------
            # ENGINE LIFECYCLE (MEMORY ONLY)
            # ----------------------------
            "engine_state": "RUNNING",
            "engine_halt_reason": None,

            # ----------------------------
            # TRADE STATE (SINGLE TRADE ONLY)
            # ----------------------------
            "open_position": None,

            # ----------------------------
            # TELEGRAM TRADE PANEL
            # ----------------------------
            "active_trade_panel_message_id": None,

            # ----------------------------
            # DAILY USD STATE (UTC-BASED)
            # ----------------------------
            "current_utc_day": None,
            "daily_realized_pnl": 0.0,
            "daily_peak_pnl": 0.0,
            "daily_loss_floor_usd": None,
            "daily_highest_unrealized_usd": 0.0,

            # ----------------------------
            # META
            # ----------------------------
            "last_trade": None,
            "last_heartbeat_utc": None,
            "heartbeat_count": 0,
            "shutdown_requested": False,
        }

    # ==================================================
    # READ HELPERS
    # ==================================================

    def get_open_position(self):
        return self.state.get("open_position")

    def update_open_position(self, open_position: dict):
        self.state["open_position"] = open_position

    def clear_open_position(self):
        self.state["open_position"] = None

    def get_state(self):
        """
        Return shallow copy of state.
        """
        return copy.deepcopy(self.state)

    # ==================================================
    # LOAD / SAVE
    # ==================================================

    def load(self):
        """
        Load state from disk.
        If file does not exist, keep defaults.
        """

        if not os.path.exists(self.filename):
            return

        try:
            with open(self.filename, "r") as f:
                loaded = json.load(f)

            # Basic structural validation
            if not isinstance(loaded, dict):
                raise ValueError("STATE_CORRUPTED_NOT_DICT")

            required_keys = [
                "balance",
                "engine_state",
                "open_position",
                "daily_realized_pnl",
                "daily_peak_pnl",
            ]

            for key in required_keys:
                if key not in loaded:
                    raise ValueError(f"STATE_CORRUPTED_MISSING_{key}")

            self.state = loaded
        except Exception as e:
            raise RuntimeError(f"STATE_LOAD_CORRUPTED | {e}")

    def save(self):
        """
        Save state to disk atomically.
        Validation occurs before persistence.
        """

        self._validate_state()

        tmp_file = self.filename + ".tmp"

        try:
            with open(tmp_file, "w") as f:
                json.dump(self.state, f, indent=2, sort_keys=True)

            os.replace(tmp_file, self.filename)

        except Exception as e:
            raise RuntimeError(f"Failed to save state: {e}")

    # ==================================================
    # TRADE UPDATE
    # ==================================================

    def update_after_trade(self, balance, open_position, last_trade):

        self.state["balance"] = balance
        self.state["open_position"] = open_position
        self.state["last_trade"] = last_trade

    # ==================================================
    # DAILY TRACKING
    # ==================================================

    def reset_daily(self, utc_day):

        self.state["current_utc_day"] = utc_day
        self.state["daily_realized_pnl"] = 0.0
        self.state["daily_peak_pnl"] = 0.0
        self.state["daily_loss_floor_usd"] = None
        self.state["daily_highest_unrealized_usd"] = 0.0

    def update_daily_realized(self, pnl_delta):

        self.state["daily_realized_pnl"] += pnl_delta

        if self.state["daily_realized_pnl"] > self.state["daily_peak_pnl"]:
            self.state["daily_peak_pnl"] = self.state["daily_realized_pnl"]

    def update_daily_loss_floor(self, value):
        self.state["daily_loss_floor_usd"] = value

    def update_daily_highest_unrealized(self, value):
        self.state["daily_highest_unrealized_usd"] = value

    def set_trade_panel_message_id(self, msg_id):
        self.state["active_trade_panel_message_id"] = msg_id

    def clear_trade_panel_message_id(self):
        self.state["active_trade_panel_message_id"] = None

    def clear_shutdown_request(self):
        self.state["shutdown_requested"] = False

    # ==================================================
    # STOP LOSS UPDATE
    # ==================================================

    def update_stop_loss(self, new_sl):
        if self.state["open_position"] is not None:
            self.state["open_position"]["stop_loss"] = new_sl

    # ==================================================
    # HEARTBEAT / SHUTDOWN
    # ==================================================

    def heartbeat(self, utc_ts):

        self.state["last_heartbeat_utc"] = utc_ts
        self.state["heartbeat_count"] += 1

    def request_shutdown(self):

        self.state["shutdown_requested"] = True

    # ==================================================
    # ENGINE LIFECYCLE MEMORY
    # ==================================================

    def set_engine_state(self, engine_state, reason=None):

        if engine_state is None:
            raise ValueError("ENGINE_STATE_CANNOT_BE_NONE")

        self.state["engine_state"] = engine_state
        self.state["engine_halt_reason"] = reason

    # ==================================================
    # INTERNAL VALIDATION
    # ==================================================

    def _validate_state(self):

        # ------------------------------------------
        # Balance
        # ------------------------------------------
        if self.state["balance"] < 0:
            raise ValueError("STATE_INVALID_BALANCE")

        # ------------------------------------------
        # Open Position Structure
        # ------------------------------------------
        open_position = self.state.get("open_position")

        if open_position is not None:

            required_fields = [
                "symbol",
                "side",
                "entry_price",
                "qty",
                "stop_loss",
                "risk_usd",
            ]

            for field in required_fields:
                if field not in open_position:
                    raise ValueError(
                        f"STATE_OPEN_POSITION_MISSING_{field}"
                    )

            if open_position["qty"] <= 0:
                raise ValueError("STATE_INVALID_POSITION_QTY")

            if open_position["risk_usd"] <= 0:
                raise ValueError("STATE_INVALID_POSITION_RISK")

            if open_position["stop_loss"] is not None:
                if open_position["stop_loss"] <= 0:
                    raise ValueError("STATE_INVALID_STOP_LOSS")

        # ------------------------------------------
        # Daily Accounting Consistency
        # ------------------------------------------
        realized = self.state["daily_realized_pnl"]
        peak = self.state["daily_peak_pnl"]

        if peak < realized:
            raise ValueError("STATE_DAILY_PEAK_INCONSISTENT")

        # ------------------------------------------
        # Engine State
        # ------------------------------------------
        if not isinstance(self.state["engine_state"], str):
            raise ValueError("STATE_INVALID_ENGINE_STATE")
