"""Engine package with lazy legacy TradingEngine compatibility."""

__all__ = ["TradingEngine"]


def __getattr__(name):
    if name == "TradingEngine":
        from .core import TradingEngine

        return TradingEngine
    raise AttributeError(name)
