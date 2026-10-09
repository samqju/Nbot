"""Credential-free bounded Binance aggTrade gap repair for V3 research."""
from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .chronological_replay import TradeEvent

USER_AGENT = "NBOT-V3-AggTrade-Recovery/1"


class AggTradeRecoveryError(RuntimeError):
    pass


def recover_agg_trades(symbol: str, *, first_id: int, last_id: int,
                       base_url: str = "https://fapi.binance.com",
                       urlopen_fn: Callable[..., Any] = urlopen,
                       timeout_seconds: float = 12.0,
                       max_rows: int = 10000) -> tuple[TradeEvent, ...]:
    if not symbol or symbol != symbol.upper() or first_id < 0 or last_id < first_id or max_rows <= 0:
        raise ValueError("AGGTRADE_RECOVERY_REQUEST_INVALID")
    wanted = last_id - first_id + 1
    if wanted > max_rows:
        raise AggTradeRecoveryError("AGGTRADE_RECOVERY_RANGE_TOO_LARGE")
    output = []
    next_id = first_id
    while next_id <= last_id:
        limit = min(1000, last_id - next_id + 1)
        query = urlencode({"symbol": symbol, "fromId": next_id, "limit": limit})
        request = Request(f"{base_url}/fapi/v1/aggTrades?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with urlopen_fn(request, timeout=timeout_seconds) as response:
                raw = response.read()
            body = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise AggTradeRecoveryError("AGGTRADE_RECOVERY_NETWORK_OR_JSON_ERROR") from exc
        if not isinstance(body, list) or not body:
            raise AggTradeRecoveryError("AGGTRADE_RECOVERY_EMPTY")
        for row in body:
            try:
                agg_id = int(row["a"])
                trade_time = int(row["T"])
                price = float(row["p"])
            except (KeyError, TypeError, ValueError) as exc:
                raise AggTradeRecoveryError("AGGTRADE_RECOVERY_PAYLOAD_INVALID") from exc
            if agg_id < next_id:
                continue
            if agg_id != next_id:
                raise AggTradeRecoveryError("AGGTRADE_RECOVERY_NONCONTIGUOUS")
            output.append(TradeEvent(symbol, agg_id, trade_time, price))
            next_id += 1
            if next_id > last_id:
                break
        if len(body) < limit and next_id <= last_id:
            raise AggTradeRecoveryError("AGGTRADE_RECOVERY_INCOMPLETE")
    return tuple(output)
