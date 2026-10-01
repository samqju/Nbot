"""Synthetic 20-symbol benchmark. Run only in an isolated checkout; never uses exchange credentials."""
import os,sys,time,json,tempfile,resource
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tests import test_v343_future_paths as f
from nbot.observation.config import observation_config_for_profile
from nbot.config.profiles import get_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.research_memory import ResearchMemoryStore
from nbot.observation.epoch import ResearchEpochProcessor
from nbot.observation.challengers import ContinuousChallengerCycle
from nbot.observation.learning_report import learning_report
os.environ["NBOT_OBSERVATION_RESOURCE_PROFILE"]="tiny"
symbols=["BTCUSDT"]+[f"COIN{i}USDT" for i in range(1,20)]
started=time.monotonic()
with tempfile.TemporaryDirectory() as td:
 os.chdir(td)
 db=EvidenceDatabase(observation_config_for_profile(get_profile("live-paper")))
 for index in range(192):
  close=100.+index;close_ms=(index+1)*f.INTERVAL-1;start=close_ms+1000
  capture=f.UniverseCapture(rows=tuple(f.UniverseRow(symbol=s,universe_rank=i+1,quote_volume_24h_usd=50000000.-i,bid_price=close*.9999,ask_price=close*1.0001,spread_pct=f.spread_pct(close*.9999,close*1.0001),mark_price=close,index_price=close,funding_rate=.0001,next_funding_time_ms=close_ms+8*3600000) for i,s in enumerate(symbols)),
   source_captures=tuple(f.SourceCapture(name,start+j*200,start+j*200+100) for j,name in enumerate(("exchange_info","ticker_24h","book_ticker","premium_index"))))
  result=db.store_live_event(event_open_ms=index*f.INTERVAL,universe_capture=capture,
   candles={s:replace(f.candle_for_index(index),symbol=s) for s in symbols},candle_errors={},
   capture_started_at_ms=close_ms+900,capture_finished_at_ms=close_ms+5000,
   server_time_before_ms=close_ms+850,server_time_after_ms=close_ms+4950)
  assert result=="COMPLETE",result
 db.store_funding_sync(start_ms=0,end_ms=192*f.INTERVAL,events=(),captured_at_ms=193*f.INTERVAL)
 memory=ResearchMemoryStore(Path("data/observation/live/research_memory.db"))
 memory.initialize(generation="BENCHMARK_TINY",generation_floor_ms=48*f.INTERVAL)
 processor=ResearchEpochProcessor(db,memory,Path.cwd(),future_client_factory=lambda cfg:f.FakePublicClient(server_time_ms=193*f.INTERVAL))
 before=time.monotonic()
 result=processor.run_once()
 assert result["status"]=="PASS",result
 trained=ContinuousChallengerCycle(memory,release_sha="a"*40).cycle()
 assert trained["action"]=="TRAIN",trained
 report=learning_report(memory)
 assert "Latest model" in report
 print(json.dumps({"synthetic_symbols":20,"raw_events":192,"epoch_events":96,
  "epoch_and_training_seconds":round(time.monotonic()-before,2),
  "total_seconds":round(time.monotonic()-started,2),
  "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
  "training_rows":trained["training_row_count"],
  "network":"simulated; no exchange requests","status":"PASS"}))
