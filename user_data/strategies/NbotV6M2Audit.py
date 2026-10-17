"""Explicit, isolated historical lookahead probe; NEVER a trading strategy.

This inherits NBOT V6's exact features, entries, exits and FreqAI hooks.
The ONLY changed behavior is permitting official Freqtrade lookahead-analysis
to force unlimited slots during its diagnostic replays. The production
NbotV6 bot_start / confirm_trade_entry remain completely untouched.
"""
from __future__ import annotations

import sys

from NbotV6 import NbotV6


class NbotV6M2Audit(NbotV6):
    def bot_start(self, **kwargs) -> None:
        config = self.config
        if config.get("dry_run") is not True:
            raise RuntimeError("M2_AUDIT_LIVE_NEVER_ALLOWED")
        exchange = config.get("exchange", {})
        if exchange.get("key") or exchange.get("secret"):
            raise RuntimeError("M2_AUDIT_CREDENTIALS_FORBIDDEN")
        if (config.get("nbot_m2_audit_only") is True
                and "lookahead-analysis" in sys.argv
                and config.get("max_open_trades") == -1
                and config.get("telegram", {}).get("enabled") is False
                and config.get("api_server", {}).get("enabled") is False):
            # Only Freqtrade's diagnostic changes risk parameters. Normal
            # trade mode cannot reach this branch, even with a config flag.
            return
        return super().bot_start(**kwargs)
