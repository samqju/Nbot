"""Bounded event-stream runner, independent of the historical research harness.

Events: universe, decision, closed_bar, labeled_watch, kill. A public or recorded
feed can provide the same contract. No live broker or credentials are enabled.
"""
import argparse
import json
import time
from pathlib import Path
from ..data import Bar
from .engine import TradingEngine
from .memory import Memory
from .learning import BrainRegistry,LearningLoop
from .shadow import ShadowBook


def run_events(engine,events,shadow=None,learning=None):
    count=0
    for event in events:
        kind=event["kind"]
        if kind=="universe":
            engine.review(event["rows"],event["time_ms"],event["now_ms"])
        elif kind=="decision":
            if shadow is not None:
                shadow.propose(event["rows"],event["quotes"],event["now_ms"],engine.memory.read()["watch"])
            engine.decide(event["rows"],event["time_ms"],event["now_ms"],event["quotes"],event.get("source_ready",False))
        elif kind=="closed_bar":
            bar=Bar(**event["bar"])
            engine.on_bar(event["symbol"],bar,event["close_ms"],event.get("funding_rate"))
            if shadow is not None:shadow.on_bar(event["symbol"],bar,event["close_ms"],event.get("funding_rate"))
        elif kind=="labeled_watch":
            row=event["row"]
            if row["label_available_ms"]>event["now_ms"]:raise ValueError("UNMATURED_WATCH_LABEL")
            engine.memory.record_outcome(event["id"],row["label_available_ms"],{"task":"watch","row":row})
        elif kind=="train" and learning is not None:
            learning.train_due(event["cutoff_ms"],event["version"])
        elif kind=="kill":engine.kill(event["reason"])
        else:raise ValueError("UNSUPPORTED_RUNTIME_EVENT:"+kind)
        count+=1
    return {"events_processed":count,"state":engine.memory.read(),"broker":"PAPER",
            "production_readiness":"NOT_ESTABLISHED"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events",type=Path)
    parser.add_argument("--public-cycles",type=int,default=0,help="Explicit bounded public paper observation cycles")
    parser.add_argument("--poll-seconds",type=int,default=300)
    parser.add_argument("--memory",type=Path,required=True)
    parser.add_argument("--model-registry",type=Path,required=True)
    parser.add_argument("--challenger-artifacts",type=Path,required=True)
    args=parser.parse_args()
    registry=BrainRegistry(args.model_registry)
    memory=Memory(args.memory)
    try:
        engine=TradingEngine(memory,registry.load())
        engine.reconcile_paper()
        shadow=ShadowBook(memory)
        learning=LearningLoop(memory,registry,args.challenger_artifacts)
        if args.events and args.public_cycles:raise ValueError("SELECT_ONE_FEED")
        if args.events:
            with args.events.open(encoding="utf-8") as stream:
                result=run_events(engine,(json.loads(line) for line in stream if line.strip()),shadow,learning)
        elif 1<=args.public_cycles<=288 and args.poll_seconds>=30:
            from .public import PublicFeed
            feed=PublicFeed()
            for cycle in range(args.public_cycles):
                snapshot=feed.snapshot()
                events=[]
                for symbol,bars in snapshot["bars"].items():
                    events.append({"kind":"closed_bar","symbol":symbol,"bar":vars(bars[-1]),"close_ms":snapshot["decision_ms"]})
                if snapshot["now_ms"]>=memory.read()["watch_expires"]:
                    events.append({"kind":"universe","rows":snapshot["watch"],"time_ms":snapshot["decision_ms"],"now_ms":snapshot["now_ms"]})
                events.append({"kind":"decision","rows":snapshot["candidates"],"time_ms":snapshot["decision_ms"],
                               "now_ms":snapshot["now_ms"],"quotes":snapshot["quotes"],"source_ready":True})
                result=run_events(engine,events,shadow,learning)
                if cycle+1<args.public_cycles:time.sleep(args.poll_seconds)
        else:raise ValueError("RECORDED_EVENTS_OR_BOUNDED_PUBLIC_CYCLES_REQUIRED")
        print(json.dumps(result,sort_keys=True,indent=2))
    finally:
        memory.close();registry.close()

if __name__=="__main__":main()
