"""V6 research: event-aware funding for next-open hypothetical trade labels.

Use real historical Binance funding EVENT RATES and a last-completed-hour
MARK PRICE proxy. Fee/slippage are still assumptions; settlement-boundary
stop fills are NOT observable in 5m OHLCV. NEVER claim executable returns.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class FundingSchedule:
    """Only history already available for outcomes/training LABELS, not features."""
    epoch_ns: np.ndarray
    rates: np.ndarray
    mark_proxy: np.ndarray

    @classmethod
    def from_candles(cls, funding: pd.DataFrame, mark: pd.DataFrame) -> "FundingSchedule":
        fd=funding.copy()
        md=mark.copy()
        for label, d, needed in (("funding",fd,("date","funding_rate")),("mark",md,("date","close"))):
            if not set(needed).issubset(d.columns) or len(d)==0:
                raise ValueError(f"MISSING_{label.upper()}_DATA")
            d["date"]=pd.to_datetime(d["date"],utc=True)
            if not d.date.is_unique or not d.date.is_monotonic_increasing:
                raise ValueError(f"NONMONOTONIC_{label.upper()}_TIMESTAMPS")
        fd["funding_rate"]=pd.to_numeric(fd["funding_rate"])
        md["close"]=pd.to_numeric(md["close"])
        if not np.isfinite(fd.funding_rate.to_numpy(dtype=float)).all():
            raise ValueError("BAD_FUNDING_RATE")
        if not (np.isfinite(md.close.to_numpy(dtype=float)).all() and (md.close>0).all()):
            raise ValueError("BAD_MARK")
        event_ns=np.asarray([timestamp.value for timestamp in fd.date], dtype=np.int64)
        # Last FINISHED 1h mark candle at the funding settlement instant.
        completed_ns=np.asarray([timestamp.value for timestamp in md.date+pd.Timedelta(hours=1)], dtype=np.int64)
        indices=np.searchsorted(completed_ns,event_ns,side="right")-1
        if (indices<0).any():
            raise ValueError("INSUFFICIENT_PAST_COMPLETED_MARK_DATA")
        return cls(event_ns,fd.funding_rate.to_numpy(dtype=float),
                   md.close.to_numpy(dtype=float)[indices])

    def hypothetical_charge(self, entry_utc, exit_utc, entry_price:float, side:int)->tuple[float,int,bool]:
        if side not in (-1,1) or not np.isfinite(entry_price) or entry_price<=0:
            raise ValueError("BAD_TRADE_ENTRY")
        start=pd.Timestamp(entry_utc)
        stop=pd.Timestamp(exit_utc)
        if start.tzinfo is None or stop.tzinfo is None or stop<start:
            raise ValueError("INVALID_TIMESTAMPS")
        a=np.searchsorted(self.epoch_ns,start.tz_convert("UTC").value,side="right")
        b=np.searchsorted(self.epoch_ns,stop.tz_convert("UTC").value,side="right")
        # Freqtrade engine funding can use different partial-period accounting.
        # This is a discrete event-only, mark-proxy approximation, not receipts.
        charge=side*np.sum(self.rates[a:b]*self.mark_proxy[a:b]/entry_price)
        # If an exit candle ends at funding settlement, stop/TP intrabar ordering
        # versus precise settlement is unknown; flag, don't claim certainty.
        ambiguous=bool(b>a and self.epoch_ns[b-1]==stop.tz_convert("UTC").value)
        return float(charge),int(b-a),ambiguous


def funding_adjusted_outcome(candles:pd.DataFrame, decision:int, side:int,
                             schedule:FundingSchedule,cost):
    from nbot_trade_outcome import outcome
    r=outcome(candles,decision,side,cost)
    if r is None:
        return None
    entry=r["entry_index"]
    exit_=r["exit_index"]
    # O(1) timestamp access, not reparsing the entire candle history for
    # each of thousands of hypothetical outcome labels.
    start=pd.Timestamp(candles["date"].iloc[entry])
    close=pd.Timestamp(candles["date"].iloc[exit_])+pd.Timedelta(minutes=5)
    if start.tzinfo is None or close.tzinfo is None:
        raise ValueError("FUNDING_LABEL_CANDLE_DATES_MUST_BE_UTC_AWARE")
    entry_price=float(candles.iloc[entry].open)
    funding_paid,events,ambiguous=schedule.hypothetical_charge(start,close,entry_price,side)
    result=dict(r)
    result.update({
        "funding_events_crossed_estimate":events,
        "funding_settlement_exit_boundary_ambiguous":ambiguous,
        "estimated_signed_funding_paid_fraction":funding_paid,
        "event_aware_label_net_return":r["net_return"]+cost.funding_reserve-funding_paid,
        "event_aware_label_total_reserved_cost":
            r["assumed_roundtrip_cost"]-cost.funding_reserve+funding_paid,
    })
    return result


def event_funding_training_labels(candles:pd.DataFrame, schedule:FundingSchedule, cost):
    """Same historical opportunity rules, funding charged at crossed events.

    Future funding is a supervised target ONLY. %-decision features and live
    signal columns are untouched. Trailing horizon labels remain NaN.
    """
    from nbot_trade_outcome import setups, priority_kind, KINDS
    if "date" not in candles:
        raise ValueError("MISSING_CANDLE_TIMESTAMPS")
    flags=setups(candles)
    code=priority_kind(flags)
    values=np.full(len(candles),np.nan,dtype=float)
    for i in range(len(candles)-cost.horizon):
        k=int(code.iloc[i])
        if k==0:
            continue
        side=-1 if KINDS[k-1].endswith("_short") else 1
        result=funding_adjusted_outcome(candles,i,side,schedule,cost)
        if result is not None:
            values[i]=result["event_aware_label_net_return"]
    result=candles.copy()
    result["&-trade_net_return"]=values
    return result
