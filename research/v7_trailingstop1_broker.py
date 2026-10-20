"""Conservative 1%-distance trailing-stop historical paper broker.

No same-candle future-high ratchet: stop active for a bar is determined
by COMPLETED PREVIOUS bars only. An earlier bar's verified favorable
extreme updates the following bar's protective stop, never the current bar.
On LONG a +0.5% favorable high moves next-bar SL -1% -> -0.5%;
+1.0% moves it to breakeven. SHORT symmetric. The exact distance is
1% of original entry (percentage points); not 1% of running high.

This causal 5m proxy is NOT Binance native exchange trailing orders.
"""
from __future__ import annotations

from nbot_v7.runtime.broker import PaperBroker


class PreviousBarTrailingOnePercentBroker(PaperBroker):
    def submit(self,intent,policy):
        if abs(policy.stop_fraction-.01)>1e-12:
            raise ValueError("REQUIRE_FIXED_INITIAL_ONE_PERCENT_PROTECTIVE_STOP")
        p=super().submit(intent,policy)
        p["trail_best_price"]=p["entry_price"]
        p["trail_distance_fraction_of_entry"]=policy.stop_fraction
        return p

    def on_bar(self,position,bar,close_ms,policy,funding_rate=None):
        # Existing protective stop is valid when entering this bar.
        fill,p=super().on_bar(position,bar,close_ms,policy,funding_rate)
        if fill is not None:
            return fill,p
        if p["last_bar_ms"]!=bar.t:
            return fill,p
        sign=1 if p["side"]=="LONG" else -1
        best=p["trail_best_price"]
        entry=p["entry_price"]
        delta=policy.stop_fraction*entry
        if sign==1:
            best=max(best,bar.h)
            # only *tighten* protective stops and never loosen
            p["stop"]=max(p["stop"],best-delta)
            # guaranteed initial stop remains entry-1% or tighter
            if p["stop"]<entry-delta-1e-9:raise ValueError("LONG_TRAIL_LOOSENED")
        else:
            best=min(best,bar.l)
            p["stop"]=min(p["stop"],best+delta)
            if p["stop"]>entry+delta+1e-9:raise ValueError("SHORT_TRAIL_LOOSENED")
        p["trail_best_price"]=best
        return None,p
