"""Synthetic-only G4 forward runner tests. Never opens Binance sockets."""
import asyncio
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.v5.g1f_journal import digest
from nbot.v5.g4_forward_vault import ForwardSourceVault
from nbot.v5.g4_forward_capture_runner import (
    source_cohort_file,_validate_isolation,run_bounded,capture_route,main,
    G4CollectorHold,
)
from nbot.v5.g4_forward_stream_contract import forward_stream_endpoints
from tests.test_v5_g4_forward_vault import trade,quote,NOW,SYMS

def cohort():
    symbols=sorted(["BTCUSDT"]+[f"COIN{i:02d}USDT" for i in range(49)])
    identity=digest({"selection_version":"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                     "symbols":tuple(symbols)})
    return {"symbols":symbols,"cohort_digest":identity}


def mark(at=NOW):
    payload={"stream":"qntusdt@markPrice@1s",
             "data":{"e":"markPriceUpdate","E":at-100,"s":"QNTUSDT",
                     "p":"200.5","i":"200.4","P":"200.3",
                     "r":"0.0001","T":at+28800000,"st":1}}
    return json.dumps(payload,separators=(",",":")).encode()


class MockSocket:
    def __init__(self,frames,*,throw_after=False):
        self.frames=frames
        self.throw_after=throw_after
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def __aiter__(self):
        for b in self.frames:
            yield b
        if self.throw_after:
            raise OSError("forced simulated disconnect")


class MockConnector:
    def __init__(self,*,throw_after=False):
        self.calls=[]
        self.throw_after=throw_after
    def __call__(self,endpoint):
        self.calls.append(endpoint)
        if "@aggTrade" in endpoint:
            frames=[trade()]
        elif "@bookTicker" in endpoint:
            frames=[quote()]
        elif "@markPrice@1s" in endpoint:
            frames=[mark()]
        else:
            raise AssertionError("unapproved mock endpoint")
        return MockSocket(frames,throw_after=self.throw_after)


class G4RunnerTests(unittest.TestCase):
    def test_valid_frozen_exact_fifty_manifest(self):
        symbols=source_cohort_file(json.dumps(cohort()).encode())
        self.assertEqual(len(symbols),50)
        self.assertEqual(symbols[0],"BTCUSDT")

    def test_changed_symbol_list_cannot_claim_frozen_cohort(self):
        source=cohort()
        source["symbols"].pop()
        with self.assertRaisesRegex(ValueError,"G4_COHORT_NOT_APPROVED_FIFTY"):
            source_cohort_file(json.dumps(source).encode())

    def test_changed_original_g1_digest_rejected(self):
        source=cohort()
        source["cohort_digest"]="a"*64
        with self.assertRaisesRegex(ValueError,"G4_COHORT_SHA_NOT_REPRODUCIBLE"):
            source_cohort_file(json.dumps(source).encode())

    def test_bad_source_manifest_shape_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_COHORT_MANIFEST_SHAPE_INVALID"):
            source_cohort_file(b'{"symbols":[]}')
        with self.assertRaisesRegex(ValueError,"G4_COHORT_MANIFEST_INVALID"):
            source_cohort_file(b'x'*10000)

    def test_source_root_only_isolated_exact_filename_and_private(self):
        with tempfile.TemporaryDirectory(prefix="g4-forward-") as root:
            p=Path(root)
            os.chmod(p,0o700)
            _validate_isolation(p,p/"g4_raw_source.sqlite")
            with self.assertRaisesRegex(ValueError,"G4_SOURCE_DB_PATH_NOT_ISOLATED"):
                _validate_isolation(p,p/"g1g2g3.sqlite")

    def test_world_readable_source_root_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="g4-forward-") as root:
            p=Path(root)
            os.chmod(p,0o755)
            with self.assertRaisesRegex(ValueError,"G4_SOURCE_ROOT_PERMISSIONS_UNSAFE"):
                _validate_isolation(p,p/"g4_raw_source.sqlite")

    def test_dry_run_creates_no_database_or_network(self):
        with tempfile.TemporaryDirectory(prefix="g4-forward-") as root:
            p=Path(root)
            os.chmod(p,0o700)
            manifest=p/"cohort.json"
            manifest.write_text(json.dumps(cohort()))
            output=StringIO()
            with redirect_stdout(output):
                rc=main(["--cohort-manifest",str(manifest),"--source-root",
                         str(p),"--max-seconds","10","--max-frames","4"])
            self.assertEqual(rc,0)
            report=json.loads(output.getvalue())
            self.assertEqual(report["status"],"DRY_RUN_NO_NETWORK")
            self.assertEqual(report["symbols"],50)
            self.assertEqual(report["order_authority"],"NONE")
            self.assertFalse((p/"g4_raw_source.sqlite").exists())

    def test_new_batch_runner_two_routes_zero_fills(self):
        with sqlite3.connect(":memory:") as db:
            vault=ForwardSourceVault(db,symbols=SYMS)
            connector=MockConnector()
            endpoints=forward_stream_endpoints(SYMS)
            result=asyncio.run(run_bounded(
                vault=vault,endpoints=endpoints,connector=connector,
                duration_s=15,max_frames=2,max_db_mib=2,
                clock_ms=lambda:NOW))
            self.assertEqual(result["frames_seen"],2)
            self.assertEqual(result["stop_reason"],"MAX_FRAMES")
            self.assertEqual(result["scored_outcomes"],0)
            self.assertEqual(result["order_authority"],"NONE")
            self.assertEqual(result["counts"]["SOURCE_RECORDED"],2)
            self.assertEqual(len(connector.calls),2)

    def test_complete_three_public_source_routes_no_trade_authority(self):
        with sqlite3.connect(":memory:") as db:
            vault=ForwardSourceVault(db,symbols=SYMS)
            connector=MockConnector()
            outcome=asyncio.run(run_bounded(
                vault=vault,endpoints=forward_stream_endpoints(SYMS),
                connector=connector,duration_s=15,max_frames=3,
                max_db_mib=2,clock_ms=lambda:NOW))
            self.assertEqual(outcome["frames_seen"],3)
            self.assertEqual(outcome["counts"]["SOURCE_RECORDED"],3)
            self.assertEqual(len(connector.calls),3)
            self.assertEqual(outcome["scored_outcomes"],0)
            self.assertEqual(outcome["order_authority"],"NONE")

    def test_invalid_max_duration_never_starts_network(self):
        vault=ForwardSourceVault(sqlite3.connect(":memory:"),symbols=SYMS)
        with self.assertRaisesRegex(ValueError,"G4_FORWARD_RESOURCE_BOUNDS_INVALID"):
            asyncio.run(run_bounded(vault=vault,endpoints=forward_stream_endpoints(SYMS),
                                    connector=MockConnector(),duration_s=MAX_S,
                                    max_frames=2,max_db_mib=2))

    def test_source_retries_exhausted_is_explicit(self):
        async def check():
            db=sqlite3.connect(":memory:")
            try:
                v=ForwardSourceVault(db,symbols=SYMS)
                stop=asyncio.Event()
                budget={"frames":0,"max_frames":100,"db_path":None,
                        "max_db_bytes":999999,"source_errors":[],"reached":None}
                await capture_route(route="market_aggtrade",endpoint="mock@aggTrade",
                                    vault=v,connector=MockConnector(throw_after=True),
                                    clock_ms=lambda:NOW,stop=stop,
                                    budget=budget,max_reconnects=1)
                self.assertEqual(budget["reached"],
                                 "SOURCE_ROUTE_RETRIES_EXHAUSTED_market_aggtrade")
                self.assertTrue(stop.is_set())
                self.assertEqual(v.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)
            finally:
                db.close()
        asyncio.run(check())

    def test_observer_does_not_grant_learning_authority(self):
        vault=ForwardSourceVault(sqlite3.connect(":memory:"),symbols=SYMS)
        x=vault.audit()
        self.assertEqual(x["model_training_authority"],"NONE")
        self.assertEqual(x["scored_outcomes"],0)

    def test_no_network_opt_in_default_even_if_path_exists(self):
        with tempfile.TemporaryDirectory(prefix="g4-forward-") as root:
            p=Path(root);os.chmod(p,0o700)
            manifest=p/"cohort.json";manifest.write_text(json.dumps(cohort()))
            (p/"g4_raw_source.sqlite").write_bytes(b"not sqlite")
            captured=StringIO()
            with redirect_stdout(captured):
                result=main(["--cohort-manifest",str(manifest),
                             "--source-root",str(p)])
            self.assertEqual(result,0)
            self.assertEqual((p/"g4_raw_source.sqlite").read_bytes(),b"not sqlite")


MAX_S=3601

if __name__=="__main__":
    unittest.main()
