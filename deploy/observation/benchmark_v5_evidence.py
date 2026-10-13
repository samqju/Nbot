"""Offline synthetic journal benchmark; no VPS or Binance capacity claim."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from nbot.observation.v5_live_evidence import LiveEvidenceBridge, _encode


def run(count):
    with tempfile.TemporaryDirectory() as td:
        symbols=[f'TEST{i}USDT' for i in range(20)]
        b=LiveEvidenceBridge(Path(td)/'v5'/'bench.db',symbols=symbols,clock=lambda:0)
        b.initialize()
        for symbol in symbols:
            b.connected(symbol)
            row={'e':'depthUpdate','s':symbol,'E':100,'T':100,'U':100,'u':100,'pu':99,'b':[],'a':[]}
            b.ingest(row,110)
            b.snapshot(symbol,{'lastUpdateId':100,'T':100,
                'bids':[[str(100-i*.01),'2'] for i in range(1000)],
                'asks':[[str(101+i*.01),'2'] for i in range(1000)]},120)
        # Idle large books + one-symbol trade mutations match the audit shape.
        timings=[]
        tracemalloc.start()
        start=time.perf_counter()
        for i in range(count):
            t=200+i
            row={'e':'aggTrade','s':symbols[0],'E':t,'T':t,'a':i,'f':i*2,'l':i*2+1,'p':'100','q':'1','m':False}
            tick=time.perf_counter(); b.ingest(row,t+1); timings.append(time.perf_counter()-tick)
        elapsed=time.perf_counter()-start
        _,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
        size=sum(p.stat().st_size for p in b.path.parent.glob('*'))
        with b._connect() as c:
            checkpoint=c.execute('SELECT length(state) FROM checkpoint').fetchone()[0]
            journal=c.execute('SELECT sum(length(event)),count(*) FROM journal').fetchone()
        restart=time.perf_counter()
        restored=LiveEvidenceBridge(b.path,symbols=symbols,clock=lambda:0); restored.initialize()
        return {'scenario':'20 symbols, 1000 levels/side, zero hypotheses, one-symbol trades',
                'events':count,'elapsed_s':elapsed,'events_per_s':count/elapsed,
                'p95_ms':sorted(timings)[int(.95*len(timings))-1]*1000,
                'p99_ms':sorted(timings)[int(.99*len(timings))-1]*1000,
                'traced_peak_bytes':peak,'db_and_wal_bytes':size,
                'checkpoint_bytes':checkpoint,'journal_bytes':journal[0],
                'journal_rows':journal[1],'restart_s':time.perf_counter()-restart,
                'host':'synthetic desktop only; tracemalloc is not process RSS',
                'durability':'SQLite WAL/FULL, one durable event per transaction'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events',type=int,default=100)
    args=parser.parse_args()
    if not 100<=args.events<=10000:parser.error('events must be 100..10000')
    print(json.dumps(run(args.events),indent=2))
