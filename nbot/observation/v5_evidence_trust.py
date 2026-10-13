"""V3 trust boundary. No public Binance path/funding certification exists here.

Legacy SCORED rows remain legacy rows; they are never upgraded by this module.
The certified consumer is deliberately unavailable until a sufficient proof
validator and source contract are independently reviewed and implemented.
"""
from __future__ import annotations

from .v5_accounting import ENTRY_FEE_RATE, EXIT_FEE_RATE, ENTRY_SLIPPAGE_RATE, EXIT_SLIPPAGE_RATE

CONTRACT = "NBOT_V5_EVIDENCE_TRUST_V3"
RECEIVED_EVIDENCE = "RECEIVED_EVIDENCE"
OBSERVED_STREAM = "OBSERVED_STREAM"
CERTIFIED_PATH = "CERTIFIED_PATH"
UNSCORABLE = "UNSCORABLE"
REVOKED = "REVOKED"
CERTIFICATION_AVAILABLE = False


def require_certified_sample(sample, *, purpose):
    """Shared consumer guard for training, promotion and performance claims.

No caller-supplied status, boolean, or proof dictionary can enable this gate.
"""
    if purpose not in {"TRAINING", "CHAMPION", "PROMOTION", "PERFORMANCE"}:
        raise ValueError("V5_CONSUMER_PURPOSE_INVALID")
    raise ValueError("V5_CERTIFIED_PATH_VALIDATOR_UNAVAILABLE")


def observed_costs(entry, arm, events):
    """Known reference-price costs; funding and after-funding returns stay null.

Observed settlement sum is a diagnostic, never a complete funding charge.
"""
    direction = 1 if entry.side == "LONG" else -1
    risk = entry.one_r_price * entry.quantity
    gross = direction * (arm.exit_price - entry.entry_price) * entry.quantity
    fees = entry.quantity * (entry.entry_price * ENTRY_FEE_RATE + arm.exit_price * EXIT_FEE_RATE)
    slip = entry.quantity * (entry.entry_price * ENTRY_SLIPPAGE_RATE + arm.exit_price * EXIT_SLIPPAGE_RATE)
    known = [e for e in events if entry.entry_time_ms < e["time_ms"] < arm.exit_time_ms]
    return {
        "contract": CONTRACT, "exit_fill_price": arm.exit_price,
        "gross_quote": gross, "gross_r": gross / risk,
        "fees_quote": fees, "slippage_quote": slip,
        "before_funding_r": (gross - fees - slip) / risk,
        "observed_funding_quote": sum(-direction * e["rate"] * e["mark_price"] * entry.quantity for e in known),
        "observed_settlements": known, "funding_coverage": "UNPROVEN",
        "funding_quote": None, "funding_r": None, "net_quote": None, "net_r": None,
    }
