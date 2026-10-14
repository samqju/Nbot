"""V4-inspired constant-space independent G4 as-of quote audit.

No ephemeral per-frame SQLite view, no retained tick list, no economic fills.
The entire original V5 compressed source chain is independently read before
any quote is exposed. Supports many original decision times per source pass.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json

from nbot.v5.g4_segmented_source import read_segments
from nbot.v5.g4_forward_entry_quote import OriginalEntryQuote
from nbot.v5.g4_forward_stream_contract import verify_frame


class VerifiedSegmentQuotes:
    """Freeze a bounded original source prefix for <=300 as-of requests."""

    def __init__(self, root, *, symbols, requests):
        symbols=tuple(sorted(symbols))
        requests=tuple(requests)
        if (len(symbols)!=50 or "BTCUSDT" not in symbols
                or len(requests)>300 or len(requests)!=len(set(requests))
                or any(not isinstance(pair,tuple) or len(pair)!=2
                       or pair[0] not in symbols or type(pair[1]) is not int
                       or pair[1]<=0 for pair in requests)):
            raise ValueError("G4_SEGMENT_QUOTES_REQUESTS_INVALID")
        self.symbols=symbols
        self.requests=requests
        self.head_sha256="0"*64
        self.frame_count=0
        by_symbol=defaultdict(list)
        self.state={}
        for key in requests:
            by_symbol[key[0]].append(key)
            self.state[key]={"epoch":None,"active":False,
                             "tainted":False,"latest":None}
        for rec,raw in read_segments(root,symbols):
            self.head_sha256=rec["chain_sha"]
            if rec["route"]!="public_bookticker":
                continue
            kind,at,epoch=rec["kind"],rec["at_ms"],rec["epoch"]
            if kind in ("OPEN","CLOSED","ABRUPT_RESTART_HOLD"):
                for item in self.state.values():
                    if at>item["_decision"] if "_decision" in item else False:
                        continue
                # A route marker at/before a given decision invalidates
                # any quote from a prior local WSS epoch.
                for key,item in self.state.items():
                    if at>key[1]:
                        continue
                    if kind=="OPEN":
                        item.update(epoch=epoch,active=True,tainted=False,latest=None)
                    else:
                        item.update(active=False,tainted=True,latest=None)
                continue
            if kind!="FRAME":
                raise ValueError("G4_SEGMENT_QUOTES_MARKER_INVALID")
            self.frame_count+=1
            symbol=rec["symbol"]
            if rec["state"]=="SOURCE_RECORDED":
                proof=verify_frame(
                    route="public_bookticker",raw=raw,
                    received_at_ms=at,source_epoch=epoch,
                    selected_symbols=symbols)
                if proof.state!="SOURCE_RECORDED" or proof.symbol!=symbol:
                    raise ValueError("G4_SEGMENT_QUOTES_INDEPENDENT_VERIFICATION_HOLD")
            for key in by_symbol.get(symbol,()):
                item=self.state[key]
                if at>key[1]:
                    continue
                if rec["state"]!="SOURCE_RECORDED":
                    item.update(tainted=True,latest=None)
                    continue
                if not item["active"] or epoch!=item["epoch"]:
                    item.update(tainted=True,latest=None)
                    continue
                if not item["tainted"] and at>=key[1]-5000:
                    item["latest"]=(rec,raw)
        # This proof head is only assigned after read_segments has verified
        # every segment; no half-audited source can yield a quote.
        self.audit_state="PASS"
        self.source_grade="ORIGINAL_LOCAL_WSS_NOT_EXCHANGE_SIGNED"
        self.order_authority="NONE"

    def asof(self, symbol, decision_at_ms, max_age_ms):
        if (type(max_age_ms) is not int or not 0<=max_age_ms<=5000):
            raise ValueError("G4_SEGMENT_QUOTE_MAX_AGE_INVALID")
        def hold(code):
            return OriginalEntryQuote("HOLD",(code,),symbol,decision_at_ms)
        item=self.state.get((symbol,decision_at_ms))
        if item is None:
            return hold("G4_SEGMENT_QUOTE_UNDECLARED_DECISION")
        if item["tainted"] or not item["active"]:
            return hold("G4_SEGMENT_QUOTE_SOURCE_HELD_OR_DISCONNECTED")
        if item["latest"] is None:
            return hold("G4_SEGMENT_QUOTE_MISSING")
        receipt,raw=item["latest"]
        at=receipt["at_ms"]
        if at<decision_at_ms-max_age_ms:
            return hold("G4_SEGMENT_QUOTE_STALE")
        try:
            data=json.loads(raw)["data"]
            bid,ask=data["b"],data["a"]
        except (ValueError,KeyError,TypeError,UnicodeError):
            return hold("G4_SEGMENT_QUOTE_CORRUPT")
        return OriginalEntryQuote(
            "LOCAL_SOURCE_QUOTE",(),symbol,at,
            bid=bid,ask=ask,
            receipt_sha256=hashlib.sha256(raw).hexdigest(),
            source_epoch=receipt["epoch"],
            chain_head_sha256=self.head_sha256)
