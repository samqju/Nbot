"""Online independent shadow outcomes; no wallet slot cap and no order authority."""
from hashlib import sha256
import json
from .broker import PaperBroker
from .risk import RiskPolicy


class ShadowBook:
    def __init__(self,memory,policy=None):
        self.memory=memory
        self.policy=policy or RiskPolicy()
        self.broker=PaperBroker()
        memory.conn.executescript("""
        CREATE TABLE IF NOT EXISTS shadow(id TEXT PRIMARY KEY,symbol TEXT,decision_ms INTEGER,row_json TEXT,position TEXT,status TEXT);
        CREATE INDEX IF NOT EXISTS shadow_active ON shadow(symbol,status);
        """)

    def propose(self,rows,quotes,now_ms,watch_symbols,control_probability=.1):
        if not 0<control_probability<=1:raise ValueError("INVALID_CONTROL_PROBABILITY")
        for row in rows:
            if row["decision_ms"]>now_ms or now_ms-row["decision_ms"]>self.policy.max_age_ms:
                raise ValueError("STALE_SHADOW_PROPOSAL")
            identity={k:row[k] for k in ("decision_ms","symbol","side","family")}
            key=sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
            # Sample outside watchlist by symbol/time, preserving whole groups.
            sample=sha256((str(row["decision_ms"])+row["symbol"]).encode()).digest()
            if row["symbol"] not in watch_symbols and int.from_bytes(sample[:8],"big")/2**64>=control_probability:
                continue
            quote=quotes.get(row["symbol"])
            if quote is None:continue
            position=self.broker.submit({"id":key,"time_ms":now_ms,"symbol":row["symbol"],
                                        "side":row["side"],"quote":quote},self.policy)
            saved=dict(row)
            saved["sampling_probability"]=1 if row["symbol"] in watch_symbols else control_probability
            self.memory.conn.execute("INSERT OR IGNORE INTO shadow VALUES(?,?,?,?,?,?)",
                (key,row["symbol"],row["decision_ms"],json.dumps(saved,sort_keys=True),json.dumps(position),"OPEN"))

    def on_bar(self,symbol,bar,close_ms,funding_rate=None):
        rows=self.memory.conn.execute("SELECT id,row_json,position FROM shadow WHERE symbol=? AND status='OPEN'",(symbol,)).fetchall()
        matured=0
        for identity,raw,position in rows:
            position=json.loads(position)
            # Source outage means no fabricated continuous path or win/loss.
            previous=position["last_bar_ms"]
            if previous is not None and bar.t>previous+(close_ms-bar.t):
                self.memory.conn.execute("UPDATE shadow SET status='CENSORED_SOURCE_GAP' WHERE id=?",(identity,))
                continue
            result,position=self.broker.on_bar(position,bar,close_ms,self.policy,funding_rate)
            if result is None:
                self.memory.conn.execute("UPDATE shadow SET position=? WHERE id=?",(json.dumps(position),identity))
                continue
            row=json.loads(raw)
            row.update(label_available_ms=close_ms,net=result["net_usdt"]/self.policy.notional_usdt,
                       quality="PAPER_BAR_PROXY",exit_ms=close_ms,
                       mfe_pct=result["mfe_pct"],mae_pct=result["mae_pct"],
                       mfe_bar_close_ms=result["mfe_bar_close_ms"],mae_bar_close_ms=result["mae_bar_close_ms"])
            self.memory.conn.execute("BEGIN IMMEDIATE")
            try:
                self.memory.record_outcome("shadow:"+identity,close_ms,{"task":"opportunity","row":row,"fill":result})
                self.memory.conn.execute("UPDATE shadow SET status='MATURED',position=? WHERE id=?",(json.dumps(position),identity))
                self.memory.conn.execute("COMMIT")
            except BaseException:
                self.memory.conn.execute("ROLLBACK")
                raise
            matured+=1
        return matured
