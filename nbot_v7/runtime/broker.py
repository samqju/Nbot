"""Broker interfaces: deterministic paper fills and separately guarded live transport."""
from dataclasses import dataclass
from math import isfinite


class PaperBroker:
    mode="PAPER"

    def submit(self,intent,policy):
        sign=1 if intent["side"]=="LONG" else -1
        price=intent["quote"]*(1+sign*policy.slippage_each)
        qty=policy.notional_usdt/price
        return {**intent,"entry_price":price,"quantity":qty,
                "entry_fee":qty*price*policy.fee_each,"funding_net":0.0,
                "stop":price*(1-sign*policy.stop_fraction),
                "target":price*(1+sign*policy.take_fraction),
                "deadline_ms":intent["time_ms"]+policy.max_hold_ms,
                "last_bar_ms":None,"broker_mode":"PAPER","mfe":0.0,"mae":0.0,
                "mfe_bar_close_ms":None,"mae_bar_close_ms":None}

    def on_bar(self,position,bar,close_ms,policy,funding_rate=None):
        if position["last_bar_ms"] is not None and bar.t<=position["last_bar_ms"]:
            return None,position
        if bar.t<position["time_ms"]:
            return None,position
        sign=1 if position["side"]=="LONG" else -1
        p=dict(position)
        p["last_bar_ms"]=bar.t
        if funding_rate is not None:
            if not isfinite(funding_rate):raise ValueError("INVALID_FUNDING_HOLD")
            p["funding_net"]-=sign*p["quantity"]*bar.o*funding_rate
        stop=bar.l<=p["stop"] if sign==1 else bar.h>=p["stop"]
        target=bar.h>=p["target"] if sign==1 else bar.l<=p["target"]
        favorable=(bar.h/p["entry_price"]-1) if sign==1 else (1-bar.l/p["entry_price"])
        adverse=(bar.l/p["entry_price"]-1) if sign==1 else (1-bar.h/p["entry_price"])
        if not (stop and target) and favorable>p["mfe"]:
            p.update(mfe=favorable,mfe_bar_close_ms=close_ms)
        if adverse<p["mae"]:p.update(mae=adverse,mae_bar_close_ms=close_ms)
        price=None
        reason=None
        if stop:
            price=min(bar.o,p["stop"]) if sign==1 else max(bar.o,p["stop"])
            reason="STOP_AMBIGUOUS" if target else "STOP"
        elif target:
            price=p["target"]
            reason="TARGET"
        elif close_ms>=p["deadline_ms"]:
            price=bar.c
            reason="HORIZON"
        if price is None:return None,p
        fill=price*(1-sign*policy.slippage_each)
        exit_fee=p["quantity"]*fill*policy.fee_each
        net=sign*p["quantity"]*(fill-p["entry_price"])-p["entry_fee"]-exit_fee+p["funding_net"]
        return {"id":p["id"],"available_ms":close_ms,"net_usdt":net,
                "entry_price":p["entry_price"],"exit_price":fill,"quantity":p["quantity"],
                "fees_usdt":p["entry_fee"]+exit_fee,"funding_net_usdt":p["funding_net"],
                "mfe_pct":p["mfe"],"mae_pct":p["mae"],
                "mfe_bar_close_ms":p["mfe_bar_close_ms"],"mae_bar_close_ms":p["mae_bar_close_ms"],
                "path_quality":"BAR_BOUNDS_NOT_TICK_EXECUTION",
                "reason":reason,"authority":"PAPER_BAR_PROXY","symbol":p["symbol"]},p


@dataclass(frozen=True)
class LivePermit:
    authorized:bool=False
    expires_ms:int=0
    max_notional_usdt:float=0
    authority_reference:str=""


class GuardedLiveBroker:
    """Requires an injected, tested venue transport; never loads real credentials.

    Transport must durably reconcile idempotent client IDs and protective orders.
    V7 has NO live permit. This interface fails closed until separately approved.
    """
    mode="LIVE"
    def __init__(self,transport=None,permit=None):
        self.transport=transport
        self.permit=permit or LivePermit()

    def submit(self,intent,policy):
        p=self.permit
        if (not p.authorized or not p.authority_reference or intent["time_ms"]>=p.expires_ms
            or policy.notional_usdt>p.max_notional_usdt or self.transport is None):
            raise PermissionError("LIVE_ORDER_AUTHORITY_DISABLED")
        return self.transport.submit_protected_idempotent(intent,policy)

    def reconcile(self,client_id):
        if not self.permit.authorized or self.transport is None:
            raise PermissionError("LIVE_RECONCILIATION_AUTHORITY_DISABLED")
        return self.transport.reconcile(client_id)
