# execution/exceptions.py

class OperationalExchangeError(RuntimeError):
    """
    External, uncontrollable exchange failure:
    - websocket closed
    - REST unavailable
    - auth / permission
    """
    pass
