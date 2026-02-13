# ==========================================================
# CONFIGURATION FILE
# ==========================================================
# POLICY ONLY.
# No dynamic logic.
# No derived values.
#
# This module self-validates on import.
# ==========================================================

# ================================
# RISK & CAPITAL POLICY
# ================================

RISK_PER_TRADE_USD = 10.0
RISK_TOLERANCE_PCT = 10.0

# ================================
# NOTIONAL POLICY
# ================================

MAX_NOTIONAL_USD = 1000.0
NOTIONAL_TOLERANCE_PCT = 1.0

# ================================
# LEVERAGE POLICY
# ================================

LEVERAGE = 5

# ================================
# SAFETY CONTROLS
# ================================

GLOBAL_KILL_SWITCH = False

# ================================
# ORDER EXECUTION POLICY
# ================================

ENTRY_SLIPPAGE_PCT = 1.0
MAX_SPREAD_PCT = 0.25

# ================================
# SYSTEM HALT POLICY
# ================================

HALT_ON_RISK_BREACH = True


# ==========================================================
# CONFIG VALIDATION (IMPORT-TIME GUARD)
# ==========================================================

def _validate():
    if RISK_PER_TRADE_USD <= 0:
        raise ValueError("CONFIG_INVALID: RISK_PER_TRADE_USD")

    if not (0 <= RISK_TOLERANCE_PCT <= 20):
        raise ValueError("CONFIG_INVALID: RISK_TOLERANCE_PCT")

    if MAX_NOTIONAL_USD <= 0:
        raise ValueError("CONFIG_INVALID: MAX_NOTIONAL_USD")

    if not (0 <= NOTIONAL_TOLERANCE_PCT <= 5):
        raise ValueError("CONFIG_INVALID: NOTIONAL_TOLERANCE_PCT")

    if LEVERAGE <= 0:
        raise ValueError("CONFIG_INVALID: LEVERAGE")

    if not (0 <= ENTRY_SLIPPAGE_PCT <= 10):
        raise ValueError("CONFIG_INVALID: ENTRY_SLIPPAGE_PCT")

    if not (0 <= MAX_SPREAD_PCT <= 5):
        raise ValueError("CONFIG_INVALID: MAX_SPREAD_PCT")


_validate()
del _validate
