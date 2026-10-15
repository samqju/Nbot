"""Offline continuous G4 collector supervision; mocked public sockets only."""
import asyncio
from contextlib import closing,redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nbot.v5.g4_forward_capture_runner import (
    run_bounded,capture_route,main)
from nbot.v5.g4_forward_stream_contract import forward_stream_endpoints
from nbot.v5.g4_forward_vault import ForwardSourceVault
from tests.test_v5_g4_forward_capture_runner import MockConnector,cohort
from tests.test_v5_g4_forward_vault import NOW,SYMS,trade


class G4ContinuousSupervisorTests(unittest.TestCase):
    def test_open_duration_remains_hard_locked_on_public_route_retries(self):
        with closing(sqlite3.connect(":memory:")) as db:
            v=ForwardSourceVault(db,symbols=SYMS)
            result=asyncio.run(run_bounded(
                vault=v,endpoints=forward_stream_endpoints(SYMS),
                connector=MockConnector(throw_after=True),
                duration_s=0,max_frames=0,max_db_mib=2,
                sustained=True,clock_ms=lambda:NOW))
            self.assertTrue(result["continuous_observation"])
            self.assertTrue(result["source_errors"])
            self.assertEqual(result["g4_scientific_accepted"],False)
            self.assertEqual(result["order_authority"],"NONE")

    def test_explicit_life_without_network_optin_refused(self):
        with TemporaryDirectory(prefix="g4-forward-synthetic-") as tmp:
            root=Path(tmp);os.chmod(root,0o700)
            manifest=root/"cohort.json"
            manifest.write_text(json.dumps(cohort()))
            output=StringIO()
            with redirect_stdout(output):
                rc=main(["--cohort-manifest",str(manifest),
                         "--source-root",str(root),"--continuous-observe",
                         "--sustained-source","--max-seconds","0",
                         "--max-frames","0","--max-db-mib","512"])
            self.assertEqual(rc,2)
            self.assertIn("G4_CONTINUOUS_OWNER_RESOURCE_RELEASE_INVALID",
                          output.getvalue())
            self.assertFalse(list(root.glob("*.sqlite*")))

    def test_window_frame_cap_is_fail_closed_not_silent_drop(self):
        async def check():
            with closing(sqlite3.connect(":memory:")) as db:
                vault=ForwardSourceVault(db,symbols=SYMS)
                stop=asyncio.Event()
                budget={"frames":0,"max_frames":None,
                        "db_path":None,"max_db_bytes":1024*1024,
                        "source_errors":[],"reached":None,
                        "window_start_ms":NOW,"window_frames":0,
                        "frame_rate_cap":1}
                await capture_route(
                    route="market_aggtrade",endpoint="mock@aggTrade",
                    vault=vault,connector=MockConnector(throw_after=True),
                    clock_ms=lambda:NOW,stop=stop,budget=budget,
                    max_reconnects=2)
                self.assertTrue(stop.is_set())
                self.assertEqual(budget["reached"],"SOURCE_FRAME_RATE_HOLD")
                self.assertEqual(budget["frames"],1)
        asyncio.run(check())

    def test_periodic_checkpoint_exception_closes_source_with_hold(self):
        class SlowSocket:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return False
            async def __aiter__(self):
                yield trade()
                await asyncio.sleep(3)
        with closing(sqlite3.connect(":memory:")) as db:
            vault=ForwardSourceVault(db,symbols=SYMS)
            original=vault.flush
            with patch.object(vault,"flush",
                              side_effect=[ValueError("DISK_CAP"),None]):
                r=asyncio.run(run_bounded(
                    vault=vault,endpoints=forward_stream_endpoints(SYMS),
                    connector=lambda endpoint:SlowSocket(),duration_s=2,
                    max_frames=100,max_db_mib=2,clock_ms=lambda:NOW))
            self.assertEqual(r["stop_reason"],"SOURCE_CHECKPOINT_HOLD")
            self.assertTrue(any("CHECKPOINT_" in e for e in r["source_errors"]))
            self.assertFalse(r["g4_scientific_accepted"])
            self.assertEqual(r["order_authority"],"NONE")


if __name__=="__main__":
    unittest.main()
