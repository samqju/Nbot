# ================================
# CONFIGURATION FILE
# ================================
# This file defines global settings.
# It contains NO logic.
# This file defines POLICY ONLY.
# No sizing logic, no dynamic risk, no derived values.

SIM_START_BALANCE = 10000.0  # fake USD

# ================================
# RISK & CAPITAL POLICY (PHASE C.0)
# ================================

# Fixed dollar risk per trade (independent of capital)
RISK_PER_TRADE_USD = 6.0

# Allowed tolerance due to slippage / gaps (percent)
RISK_TOLERANCE_PCT = 4.0

# -------------------------------
# NOTIONAL POLICY
# -------------------------------
# Target notional exposure per trade (USD)
MAX_NOTIONAL_USD = 300.0

# Allowed deviation from notional (percent)
NOTIONAL_TOLERANCE_PCT = 1.0

# -------------------------------
# LEVERAGE POLICY
# -------------------------------

# Fixed leverage (no scaling, no overrides)
LEVERAGE = 5

# -------------------------------
# SAFETY CONTROLS
# -------------------------------
# If True, bot will refuse to trade no matter what

GLOBAL_KILL_SWITCH = False

# -------------------------------
# ORDER EXECUTION POLICY
# -------------------------------

# Entry orders
ENTRY_ORDER_TYPE = "LIMIT"
ENTRY_SLIPPAGE_PCT = 1.0

# ------------------------------------------------
# STEP 6.7 — Spread / Illiquidity Guard
# ------------------------------------------------
# Maximum allowed bid-ask spread (percent)
MAX_SPREAD_PCT = 0.25

# Exit orders
EXIT_NORMAL_ORDER_TYPE = "LIMIT"
EXIT_EMERGENCY_ORDER_TYPE = "MARKET"
EXIT_SLIPPAGE_PCT = 1.0

# -------------------------------
# SYSTEM HALT POLICY
# -------------------------------

# Halt system on risk contract breach
HALT_ON_RISK_BREACH = True

STOP_REASON_RISK_FAILURE = "RISK_FAILURE"
STOP_REASON_UNKNOWN_ERROR = "UNKNOWN_ERROR"
