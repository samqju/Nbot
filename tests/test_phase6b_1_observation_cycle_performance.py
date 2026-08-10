import tempfile
import threading
import unittest
from pathlib import Path

from strategy.learning_runtime_state import LearningRuntimeStateStore
from strategy.strategy import Strategy
from strategy.virtual_trade_engine import VirtualTradeEngine


class RuntimeStoreProbe:
    def __init__(self):
        self.section_writes = []
        self.combined_writes = []

    def replace_section(self, section, rows):
        self.section_writes.append((section, list(rows)))

    def replace_sections(self, sections):
        self.combined_writes.append({
            key: list(rows)
            for key, rows in sections.items()
        })


class VirtualStateProbe:
    def __init__(self, rows=None, *, dirty=True):
        self.rows = list(rows or [])
        self.dirty = bool(dirty)
        self.persisted_marks = 0

    def has_dirty_state(self):
        return self.dirty

    def runtime_state_snapshot(self):
        return [dict(row) for row in self.rows]

    def mark_runtime_state_persisted(self):
        self.dirty = False
        self.persisted_marks += 1


class Phase6B1ObservationCyclePerformanceTests(unittest.TestCase):
    def test_runtime_store_replaces_two_sections_with_one_atomic_write(self):
        with tempfile.TemporaryDirectory() as root:
            store = LearningRuntimeStateStore(
                str(Path(root) / "state.json")
            )
            writes = []
            original = store._write_atomic

            def counted(document):
                writes.append(True)
                original(document)

            store._write_atomic = counted
            store.replace_sections({
                "pending_simulations": [{"id": "pending"}],
                "active_virtual_trades": [{"id": "virtual"}],
            })

            self.assertEqual(len(writes), 1)
            self.assertEqual(
                store.get_section("pending_simulations"),
                [{"id": "pending"}],
            )
            self.assertEqual(
                store.get_section("active_virtual_trades"),
                [{"id": "virtual"}],
            )

    def test_enroll_all_batches_persistence_once(self):
        engine = VirtualTradeEngine.__new__(VirtualTradeEngine)
        engine.lab_enabled = False
        engine._baseline_variant = object()
        engine.system_log = None
        engine.catalog_version = "TEST"
        engine._active_state_dirty = False

        persist_flags = []
        flushes = []

        def fake_enroll(_candidate, _variant, *, persist=True):
            persist_flags.append(persist)
            engine._active_state_dirty = True
            return True

        def fake_flush():
            flushes.append(True)
            engine._active_state_dirty = False
            return True

        engine._enroll_variant = fake_enroll
        engine.flush_active_state = fake_flush

        created = VirtualTradeEngine.enroll_all(
            engine,
            [object() for _ in range(25)],
        )

        self.assertEqual(created, 25)
        self.assertEqual(persist_flags, [False] * 25)
        self.assertEqual(len(flushes), 1)

    def test_deferred_candle_progress_does_not_rewrite_per_symbol(self):
        store = RuntimeStoreProbe()
        engine = VirtualTradeEngine.__new__(VirtualTradeEngine)
        engine.system_log = None
        engine.runtime_store = store
        engine.outcome_writer = None
        engine._lock = threading.Lock()
        engine._active_state_dirty = False
        engine._runtime_closures = 0
        engine._active = {
            "candidate-1::BASE": {
                "candidate_observation_id": "candidate-1",
                "symbol": "BTCUSDT",
                "direction": "LONG",
                "entry_price": 100.0,
                "risk_distance": 10.0,
                "stop_price": 90.0,
                "target_price": 120.0,
                "target_r": 2.0,
                "max_candles": 10,
                "candles_seen": 0,
                "mae_r": 0.0,
                "mfe_r": 0.0,
            }
        }

        finished = VirtualTradeEngine.on_candle(
            engine,
            "BTCUSDT",
            (100.0, 101.0, 99.0, 100.5),
            persist=False,
        )

        self.assertEqual(finished, [])
        self.assertEqual(store.section_writes, [])
        self.assertTrue(engine.has_dirty_state())
        self.assertEqual(
            engine._active["candidate-1::BASE"]["candles_seen"],
            1,
        )

    def test_strategy_combines_dirty_sections_at_batch_checkpoint(self):
        strategy = Strategy.__new__(Strategy)
        strategy._ml_lock = threading.Lock()
        strategy._pending_simulations = [{"id": "pending"}]
        strategy._pending_runtime_dirty = True
        strategy._learning_runtime_dirty_since_monotonic = 100.0
        strategy._learning_runtime_max_dirty_seconds = 30.0
        strategy._learning_runtime_store = RuntimeStoreProbe()
        strategy._virtual_trade_engine = VirtualStateProbe(
            [{"id": "virtual"}]
        )

        flushed = Strategy._maybe_flush_learning_runtime_progress(
            strategy,
            force=True,
            now_monotonic=101.0,
        )

        self.assertTrue(flushed)
        self.assertEqual(
            len(strategy._learning_runtime_store.combined_writes),
            1,
        )
        payload = strategy._learning_runtime_store.combined_writes[0]
        self.assertEqual(payload["pending_simulations"], [{"id": "pending"}])
        self.assertEqual(payload["active_virtual_trades"], [{"id": "virtual"}])
        self.assertFalse(strategy._pending_runtime_dirty)
        self.assertFalse(strategy._virtual_trade_engine.dirty)
        self.assertIsNone(strategy._learning_runtime_dirty_since_monotonic)


    def test_pending_simulation_add_can_defer_whole_state_rewrite(self):
        strategy = Strategy.__new__(Strategy)
        strategy._ml_lock = threading.Lock()
        strategy._pending_simulations = []
        strategy._pending_runtime_dirty = False
        strategy._learning_runtime_dirty_since_monotonic = None
        strategy._learning_runtime_max_dirty_seconds = 30.0
        strategy._learning_runtime_store = RuntimeStoreProbe()
        strategy._virtual_trade_engine = VirtualStateProbe([], dirty=False)

        simulations = []
        for index in range(85):
            simulation = {
                "candidate_observation_id": f"candidate-{index}",
                "symbol": "BTCUSDT",
                "direction": "LONG",
                "entry_price": 100.0,
                "risk_distance": 1.0,
                "candles_seen": 0,
                "mae": 0.0,
                "mfe": 0.0,
            }
            simulations.append(simulation)
            self.assertTrue(
                Strategy.add_pending_simulation(
                    strategy,
                    simulation,
                    persist=False,
                )
            )

        self.assertTrue(strategy._pending_runtime_dirty)
        self.assertEqual(
            strategy._learning_runtime_store.section_writes,
            [],
        )
        self.assertEqual(
            strategy._learning_runtime_store.combined_writes,
            [],
        )

        flushed = Strategy._maybe_flush_learning_runtime_progress(
            strategy,
            force=True,
        )

        self.assertTrue(flushed)
        self.assertEqual(
            len(strategy._learning_runtime_store.combined_writes),
            1,
        )
        self.assertEqual(
            strategy._learning_runtime_store.combined_writes[0][
                "pending_simulations"
            ],
            simulations,
        )

    def test_periodic_fallback_uses_dirty_age_not_idle_time(self):
        strategy = Strategy.__new__(Strategy)
        strategy._ml_lock = threading.Lock()
        strategy._pending_simulations = [{"id": "pending"}]
        strategy._pending_runtime_dirty = True
        strategy._learning_runtime_dirty_since_monotonic = 100.0
        strategy._learning_runtime_max_dirty_seconds = 30.0
        strategy._learning_runtime_store = RuntimeStoreProbe()
        strategy._virtual_trade_engine = VirtualStateProbe([], dirty=False)

        self.assertFalse(
            Strategy._maybe_flush_learning_runtime_progress(
                strategy,
                now_monotonic=129.9,
            )
        )
        self.assertEqual(
            strategy._learning_runtime_store.combined_writes,
            [],
        )

        self.assertTrue(
            Strategy._maybe_flush_learning_runtime_progress(
                strategy,
                now_monotonic=130.0,
            )
        )
        self.assertEqual(
            len(strategy._learning_runtime_store.combined_writes),
            1,
        )


if __name__ == "__main__":
    unittest.main()
