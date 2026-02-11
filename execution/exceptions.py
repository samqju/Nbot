# execution/exceptions.py

class OperationalExchangeError(RuntimeError):
    """
    External, uncontrollable exchange failure:
    - websocket closed
    - REST unavailable
    - auth / permission
    """
    pass

class StopAlreadyBreached(RuntimeError):
    """
    Calculated stop-loss is already breached by current market price.
    This is a market safety condition, not an exchange failure.
    """
    pass
