# ==========================================================
# Exchange Exception Contracts
# ==========================================================
# Purpose:
# - Define explicit error categories for adapter boundary
# - Separate operational failures from market safety conditions
# - Provide machine-readable error typing
#
# Design:
# - All adapter errors inherit from ExchangeError
# - Engine may react differently based on error category
# ==========================================================


class ExchangeError(RuntimeError):
    """
    Base class for all exchange-layer errors.
    """
    pass


# ----------------------------------------------------------
# Operational Failures (External / Infrastructure)
# ----------------------------------------------------------

class OperationalExchangeError(ExchangeError):
    """
    External, uncontrollable exchange failure.

    Examples:
    - WebSocket closed
    - REST timeout
    - Auth failure
    - Permission issue
    """
    pass


class EntryValidationError(ExchangeError):
    """
    Deterministic local entry rejection raised before an order is submitted.

    These failures must not enter ambiguous-order recovery because Binance
    has not received an order request.
    """
    pass


# ----------------------------------------------------------
# Market Safety Violations (Price / State based)
# ----------------------------------------------------------

class MarketStateError(ExchangeError):
    """
    Market condition makes requested action unsafe.
    """
    pass


class StopAlreadyBreached(MarketStateError):
    """
    Calculated stop-loss is already breached by current market price.
    This is a market safety condition,
    not an infrastructure failure.
    """
    pass
