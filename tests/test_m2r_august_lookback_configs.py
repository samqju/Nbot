"""Audit-only frozen August lookback experiment contract. No exchange access."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WINDOWS=(30,60,90,180)


def test_august_lookback_overlays_are_identical_except_train_window_and_identifier():
    baseline=None
    for days in WINDOWS:
        path=ROOT / "user_data" / f"config.m2r-aug2026-{days}day-funded-purged.json"
        cfg=json.loads(path.read_text())
        assert cfg["dry_run"] is True
        assert cfg["nbot_m2r_research_only"] is True
        assert cfg["nbot_m2r_purge_internal"] is True
        assert cfg["nbot_m2r_event_funding_labels"] is True
        assert cfg["nbot_live_mode"] is False
        assert cfg["nbot_paper_research_mode"] is False
        assert cfg["max_open_trades"] == 1
        assert cfg["force_entry_enable"] is False
        assert cfg["exchange"] == {"key": "", "secret": ""}
        assert cfg["telegram"]["enabled"] is False
        assert cfg["api_server"]["enabled"] is False
        ai=cfg["freqai"]
        assert ai["identifier"] == f"nbot-v6-m2r-multiwindow-aug2026-{days}d-20261017"
        assert ai["train_period_days"] == days
        assert ai["backtest_period_days"] == 7
        assert ai["data_split_parameters"] == {"test_size":0.2, "shuffle":False}
        assert ai["feature_parameters"]["label_period_candles"] == 12
        probe=copy.deepcopy(cfg)
        probe.pop("bot_name")
        probe["freqai"].pop("identifier")
        probe["freqai"].pop("train_period_days")
        if baseline is None:
            baseline=probe
        else:
            assert probe == baseline, "UNAUTHORIZED_EXTRA_DIFFERENCE_ACROSS_LOOKBACKS"
