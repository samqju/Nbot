# ================================
# STATE MODULE
# ================================
# This module stores and retrieves bot state.
# It does NOT make decisions.

# ================================
# IMPORTS
# ================================

import json
import os

# ================================
# STATE MANAGER CLASS
# ================================

class StateManager:
    """
    StateManager persists bot memory safely.
    """

    # ----------------------------
    # INITIALIZATION
    # ----------------------------
    def __init__(self, filename="bot_state.json"):
        """
        Initialize state manager.
        """
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
            "open_position": None,          # current open trade (or None)

            # ----------------------------
            # DAILY USD STATE (UTC-BASED)
            # ----------------------------
            "current_utc_day": None,
            "daily_realized_pnl": 0.0,
            "daily_peak_pnl": 0.0,
            "daily_loss_floor_usd": None,

            # ----------------------------
            # META
            # ----------------------------
            "last_trade": None,
            "last_heartbeat_utc": None,
            "heartbeat_count": 0,
            "shutdown_requested": False,
        }

    # --------------------------------------------------
    # Read helpers
    # --------------------------------------------------

    def get_open_position(self):
        """
        Return cached open position (or None).
        """
        return self.state.get("open_position")

    def update_open_position(self, open_position: dict):
        self.state["open_position"] = open_position

    def clear_open_position(self):
        self.state["open_position"] = None

    # ----------------------------
    # LOAD STATE FROM DISK
    # ----------------------------
    def load(self):
        """
        Load state from disk.
        If file does not exist, keep defaults.
        If loading fails, raise exception.
        """
        if not os.path.exists(self.filename):
            return

        try:
            with open(self.filename, "r") as f:
                self.state = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load state: {e}")

    # ----------------------------
    # SAVE STATE TO DISK
    # ----------------------------
    def save(self):
        """
        Save state to disk atomically.
        If saving fails, raise exception.
        """
        tmp_file = self.filename + ".tmp"

        try:
            with open(tmp_file, "w") as f:
                    json.dump(self.state, f, indent=2, sort_keys=True)

            os.replace(tmp_file, self.filename)
        except Exception as e:
            raise RuntimeError(f"Failed to save state: {e}")

    # ----------------------------
    # GET READ-ONLY STATE SNAPSHOT
    # ----------------------------
    def get_state(self):
        """
        Return a copy of the current state.
        Risk manager uses this.
        """
        return dict(self.state)

    # ----------------------------
    # UPDATE STATE AFTER TRADE
    # ----------------------------
    def update_after_trade(self, balance, open_position, last_trade):
        """
        Update state fields after a trade.
        """
        self.state["balance"] = balance
        self.state["open_position"] = open_position
        self.state["last_trade"] = last_trade

    # ----------------------------
    # DAILY USD TRACKING
    # ----------------------------
    def reset_daily(self, utc_day):
        self.state["current_utc_day"] = utc_day
        self.state["daily_realized_pnl"] = 0.0
        self.state["daily_peak_pnl"] = 0.0
        self.state["daily_loss_floor_usd"] = None

    def update_daily_realized(self, pnl_delta):
        self.state["daily_realized_pnl"] += pnl_delta

        if self.state["daily_realized_pnl"] > self.state["daily_peak_pnl"]:
            self.state["daily_peak_pnl"] = self.state["daily_realized_pnl"]

    # ----------------------------
    # STOP LOSS UPDATE
    # ----------------------------
    def update_stop_loss(self, new_sl):
        if self.state["open_position"] is not None:
            self.state["open_position"]["stop_loss"] = new_sl

    def update_daily_loss_floor(self, value):
        self.state["daily_loss_floor_usd"] = value

    def heartbeat(self, utc_ts):
        """
        Persist engine heartbeat.
        PASS 3.4
        """
        self.state["last_heartbeat_utc"] = utc_ts
        self.state["heartbeat_count"] += 1

    def request_shutdown(self):
        """
        Signal that a graceful shutdown has been requested.
        PASS 3.5
        """
        self.state["shutdown_requested"] = True

    # ----------------------------
    # ENGINE LIFECYCLE (MEMORY ONLY)
    # ----------------------------

    def set_engine_state(self, engine_state, reason=None):
        """
        Persist engine lifecycle state.
        NOTE:
        - Engine is the sole authority for transitions
        - StateManager only remembers the last known state
        """
        self.state["engine_state"] = engine_state
        self.state["engine_halt_reason"] = reason
