"""Unit contract for frozen 2026 long-history offline lookbacks."""
from pathlib import Path
import json, copy

ROOT=Path(__file__).resolve().parents[1]

def test_jansep_four_lookbacks_safeguards_and_cost_assumptions_are_identical():
    base=None
    for w in (30,60,90,180):
        cfg=json.loads((ROOT/"user_data"/f"config.m2r-jansep2026-{w}day-offline.json").read_text())
        assert cfg["dry_run"] is True
        assert cfg["nbot_m2r_research_only"] is True
        assert cfg["nbot_m2r_purge_internal"] is True
        assert cfg["nbot_m2r_event_funding_labels"] is True
        assert cfg["nbot_live_mode"] is False
        assert cfg["nbot_paper_research_mode"] is False
        assert cfg["max_open_trades"] == 1
        assert cfg["force_entry_enable"] is False
        assert cfg["exchange"] == {"key":"","secret":""}
        assert cfg["telegram"]["enabled"] is False
        assert cfg["api_server"]["enabled"] is False
        assert cfg["freqai"]["train_period_days"] == w
        assert cfg["freqai"]["backtest_period_days"] == 7
        assert cfg["freqai"]["identifier"] == f"nbot-v6-m2r-jansep2026-{w}d-20261017"
        assert cfg["freqai"]["data_split_parameters"] == {"test_size":.2,"shuffle":False}
        assert cfg["freqai"]["feature_parameters"]["label_period_candles"] == 12
        normalized=copy.deepcopy(cfg)
        normalized.pop("bot_name")
        normalized["freqai"].pop("identifier")
        normalized["freqai"].pop("train_period_days")
        if base is None:base=normalized
        else:assert base==normalized
