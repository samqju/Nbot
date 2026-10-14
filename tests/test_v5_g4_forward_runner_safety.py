"""Live-runner unexpected-exception fail-closed and bounded-outcome mock tests."""
import asyncio
import sqlite3
import unittest

from nbot.v5.g4_forward_capture_runner import run_bounded,capture_route
from nbot.v5.g4_forward_vault import ForwardSourceVault
from nbot.v5.g4_forward_stream_contract import forward_stream_endpoints
from tests.test_v5_g4_forward_vault import SYMS,NOW
from tests.test_v5_g4_forward_capture_runner import MockConnector
from tests.test_v5_g4_forward_vault import trade


class G4RunnerCrashSafetyTests(unittest.TestCase):
    def test_unhandled_connection_task_exception_becomes_explicit_hold(self):
        def broken(_):
            raise KeyError("simulation-of-prior-unhandled-task-error")
        with sqlite3.connect(":memory:") as db:
            vault=ForwardSourceVault(db,symbols=SYMS)
            result=asyncio.run(run_bounded(
                vault=vault,endpoints=forward_stream_endpoints(SYMS),
                connector=broken,duration_s=3,max_frames=20,
                max_db_mib=1,clock_ms=lambda:NOW))
            self.assertEqual(result["stop_reason"],"UNEXPECTED_RUNNER_TASK_HOLD")
            self.assertIn("UNEXPECTED_TASK_KeyError",result["source_errors"])
            self.assertEqual(result["audit"],"PASS")
            self.assertEqual(result["scored_outcomes"],0)
            self.assertFalse(result["g4_scientific_accepted"])

    def test_actual_websockets_connectionclosed_error_class_requires_epoch_hold(self):
        # Reproduces type family from the genuine bounded Oct 14 original
        # Binance pilot without opening any network socket in CI.
        Closed=type("ConnectionClosedError",(Exception,),
                    {"__module__":"websockets.exceptions"})
        class Socket:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return False
            async def __aiter__(self):
                yield trade()
                raise Closed("synthetic transport close")
        async def check():
            with sqlite3.connect(":memory:") as db:
                vault=ForwardSourceVault(db,symbols=SYMS)
                stop=asyncio.Event()
                budget={"frames":0,"max_frames":500,
                        "db_path":None,"max_db_bytes":99999,
                        "source_errors":[],"reached":None}
                await capture_route(
                    route="market_aggtrade",endpoint="mock market",
                    vault=vault,connector=lambda url:Socket(),
                    clock_ms=lambda:NOW,stop=stop,budget=budget,
                    max_reconnects=1)
                self.assertTrue(stop.is_set())
                self.assertEqual(
                    budget["source_errors"],
                    ["market_aggtrade:WSS_ConnectionClosedError"]*2)
                self.assertEqual(vault.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)
                self.assertEqual(budget["reached"],
                                 "SOURCE_ROUTE_RETRIES_EXHAUSTED_market_aggtrade")
        asyncio.run(check())

    def test_mock_market_stream_end_not_a_continuous_source(self):
        with sqlite3.connect(":memory:") as db:
            vault=ForwardSourceVault(db,symbols=SYMS)
            result=asyncio.run(run_bounded(
                vault=vault,endpoints=forward_stream_endpoints(SYMS),
                connector=MockConnector(throw_after=True),duration_s=5,
                max_frames=100,max_db_mib=1,clock_ms=lambda:NOW))
            self.assertTrue(result["source_errors"] or
                            result["stop_reason"].startswith("SOURCE_ROUTE_RETRIES_EXHAUSTED"))
            self.assertFalse(result["complete_four_hour_source_proven"])
            self.assertEqual(result["model_training_authority"],"NONE")

    def test_full_mock_three_route_frame_cap_not_outcome_qualification(self):
        with sqlite3.connect(":memory:") as db:
            vault=ForwardSourceVault(db,symbols=SYMS)
            result=asyncio.run(run_bounded(
                vault=vault,endpoints=forward_stream_endpoints(SYMS),
                connector=MockConnector(),duration_s=5,
                max_frames=3,max_db_mib=1,clock_ms=lambda:NOW))
            self.assertEqual(result["stop_reason"],"MAX_FRAMES")
            self.assertTrue(result["bounded_pilot_only"])
            self.assertFalse(result["g4_scientific_accepted"])
            self.assertFalse(result["complete_four_hour_source_proven"])
            self.assertEqual(result["scored_outcomes"],0)

if __name__=="__main__":
    unittest.main()
