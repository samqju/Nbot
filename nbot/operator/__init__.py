"""Best-effort NBOT V3 operator surfaces.

Operator visibility must never become capital or research authority.  Telegram,
file logging and command handling are deliberately isolated from trading and
canonical evidence state.
"""

from .telegram import TelegramClient, TelegramCommandListener, TelegramConfig, TelegramDispatcher

__all__ = ["TelegramClient", "TelegramCommandListener", "TelegramConfig", "TelegramDispatcher"]
