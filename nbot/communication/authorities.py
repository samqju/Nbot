"""Versioned non-capital recommendation authority labels.

These labels describe what Observation is permitted to recommend.  They never
create Binance order authority; Execution still owns the final local entry/risk
boundary for the active profile.
"""

TESTNET_OPERATIONAL_CANARY_AUTHORITY = "TESTNET_OPERATIONAL_CANARY_V1"
LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY = "LIVE_PAPER_OPERATIONAL_CANARY_V1"

__all__ = [
    "TESTNET_OPERATIONAL_CANARY_AUTHORITY",
    "LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY",
]
