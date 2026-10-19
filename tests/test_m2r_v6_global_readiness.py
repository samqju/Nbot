"""Read-only Stage3 readiness test with isolated synthetic filesystem (no Docker)."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import m2r_v6_global_readiness as readiness

class GlobalStage3Readiness(unittest.TestCase):
    def setUp(self):
        self.temporary=TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.source=self.root/"global-next-source"
        for folder in ("scripts","user_data/strategies","user_data/freqaimodels"):
            (self.source/folder).mkdir(parents=True)
        for path in readiness.DEFAULTS:
            x=self.source/path
            x.parent.mkdir(parents=True,exist_ok=True)
            x.write_text("x=1\n")
            x.chmod(0o644)
        runner=self.source/"scripts/m2r_v6_global_batch.py"
        runner.write_text(
            'x={"nbot_live_mode":False,"nbot_paper_research_mode":False,'
            '"nbot_v6_global_research_only":True,"freqai":{"enabled":False}}\n')
        self.pairs=[f"TEST{n:02d}/USDT:USDT" for n in range(25)]
        base={"dry_run":True,"max_open_trades":1,"stake_amount":1000,
              "exchange":{"key":"","secret":"","pair_whitelist":self.pairs}}
        (self.source/"user_data/config.json").write_text(json.dumps(base))
        history=self.root/"january-2026-public-history-stage/futures"
        history.mkdir(parents=True)
        for pair in self.pairs:
            name=pair.replace("/","_").replace(":","_")
            for suffix in ("-5m-futures.feather","-1h-funding_rate.feather",
                           "-1h-mark.feather"):
                (history/(name+suffix)).write_bytes(b"0"*1025)

    def test_absent_optional_base_research_flags_are_safe_when_overlay_is_locked(self):
        r=readiness.preflight(self.root)
        self.assertTrue(r["static_readiness_ok"],r["errors"])
        self.assertEqual(r["pair_count"],25)
        self.assertEqual(r["market_input_missing"],[])
        self.assertTrue(r["read_only"])

    def test_reject_root_only_python_before_docker(self):
        target=self.source/"user_data/strategies/NbotV6GlobalOfflineResearch.py"
        target.chmod(0o600)
        r=readiness.preflight(self.root)
        self.assertFalse(r["static_readiness_ok"])
        self.assertTrue(any("DOCKER_CANNOT_READ_PYTHON" in x for x in r["errors"]))

    def test_reject_missing_historical_funding(self):
        (self.root/"january-2026-public-history-stage/futures/TEST00_USDT_USDT-1h-funding_rate.feather").unlink()
        r=readiness.preflight(self.root)
        self.assertFalse(r["static_readiness_ok"])
        self.assertEqual(len(r["market_input_missing"]),1)

    def test_reject_live_config_or_missing_research_guard(self):
        f=self.source/"user_data/config.json"
        cfg=json.loads(f.read_text())
        cfg["nbot_live_mode"]=True
        f.write_text(json.dumps(cfg))
        r=readiness.preflight(self.root)
        self.assertIn("OFFLINE_ONLY_CONFIG_GATE",r["errors"])
        cfg["nbot_live_mode"]=False
        f.write_text(json.dumps(cfg))
        runner=self.source/"scripts/m2r_v6_global_batch.py"
        runner.write_text("x=1\n")
        r=readiness.preflight(self.root)
        self.assertFalse(r["static_readiness_ok"])
        self.assertTrue(any("MISSING_EXPLICIT_STAGE3_OVERLAY_FLAG" in x for x in r["errors"]))

if __name__=="__main__":
    unittest.main()
