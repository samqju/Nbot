from __future__ import annotations

import unittest

from nbot.exchange.contracts import CloseFill, ExchangePosition
from nbot.execution.emergency import (
    EmergencyConfig,
    EmergencyFlattenError,
    EmergencyFlattener,
)


class FakeExchange:
    def __init__(self):
        self.position = ExchangePosition("BTCUSDT", "LONG", 0.1, 100.0)
        self.close_calls = []
        self.snapshot_calls = 0
        self.snapshot_errors = []
        self.close_errors = []
        self.stay_open_attempts = 0
        self.after_close_position = None
        self.on_close = None

    def position_snapshot(self):
        self.snapshot_calls += 1
        if self.snapshot_errors:
            error = self.snapshot_errors.pop(0)
            if error is not None:
                raise error
        return self.position

    def close_position(self, symbol, side, *, reason):
        self.close_calls.append((symbol, side, reason))
        if self.on_close is not None:
            self.on_close()
        if self.close_errors:
            error = self.close_errors.pop(0)
            if error is not None:
                # Simulate an ambiguous request that may have reached exchange.
                raise error
        if self.stay_open_attempts > 0:
            self.stay_open_attempts -= 1
        else:
            self.position = self.after_close_position
        return CloseFill(
            price=101.0,
            timestamp_ms=1_700_000_000_000,
            reason=reason,
            realized_pnl_usd=1.0,
            order_ids=(f"close-{len(self.close_calls)}",),
        )


class EmergencyConfigTests(unittest.TestCase):
    def test_defaults_preserve_v2_parity(self):
        cfg = EmergencyConfig()
        self.assertEqual(cfg.max_attempts, 2)
        self.assertEqual(cfg.verify_delay_seconds, 0.5)

    def test_min_attempts_allowed(self):
        self.assertEqual(EmergencyConfig(max_attempts=1).max_attempts, 1)

    def test_max_attempts_allowed(self):
        self.assertEqual(EmergencyConfig(max_attempts=10).max_attempts, 10)

    def test_zero_delay_allowed(self):
        self.assertEqual(EmergencyConfig(verify_delay_seconds=0).verify_delay_seconds, 0)

    def test_ten_second_delay_allowed(self):
        self.assertEqual(EmergencyConfig(verify_delay_seconds=10).verify_delay_seconds, 10)

    def test_attempts_zero_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_ATTEMPTS_INVALID"):
            EmergencyConfig(max_attempts=0)

    def test_attempts_above_ten_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_ATTEMPTS_INVALID"):
            EmergencyConfig(max_attempts=11)

    def test_attempts_bool_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_ATTEMPTS_INVALID"):
            EmergencyConfig(max_attempts=True)

    def test_attempts_float_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_ATTEMPTS_INVALID"):
            EmergencyConfig(max_attempts=2.0)

    def test_negative_delay_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_VERIFY_DELAY_INVALID"):
            EmergencyConfig(verify_delay_seconds=-0.1)

    def test_delay_above_ten_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_VERIFY_DELAY_INVALID"):
            EmergencyConfig(verify_delay_seconds=10.1)

    def test_delay_bool_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_VERIFY_DELAY_INVALID"):
            EmergencyConfig(verify_delay_seconds=False)

    def test_nonfinite_delay_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_VERIFY_DELAY_INVALID"):
            EmergencyConfig(verify_delay_seconds=float("inf"))

    def test_sleep_must_be_callable(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_SLEEP_INVALID"):
            EmergencyFlattener(exchange=FakeExchange(), sleep=None)


class EmergencyFlattenTests(unittest.TestCase):
    def make(self, exchange=None, *, attempts=2, delay=0):
        self.exchange = exchange or FakeExchange()
        self.sleeps = []
        self.emergency = EmergencyFlattener(
            exchange=self.exchange,
            config=EmergencyConfig(max_attempts=attempts, verify_delay_seconds=delay),
            sleep=self.sleeps.append,
        )
        return self.emergency

    def test_already_flat_returns_without_close_write(self):
        exchange = FakeExchange()
        exchange.position = None
        self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="TEST")
        self.assertEqual(exchange.close_calls, [])
        self.assertEqual(exchange.snapshot_calls, 1)

    def test_normal_close_returns_only_after_flat_snapshot(self):
        exchange = FakeExchange()
        self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(exchange.close_calls, [("BTCUSDT", "LONG", "RISK")])
        self.assertIsNone(exchange.position)
        self.assertGreaterEqual(exchange.snapshot_calls, 2)

    def test_short_position_supported(self):
        exchange = FakeExchange()
        exchange.position = ExchangePosition("ETHUSDT", "SHORT", 2.0, 200.0)
        self.make(exchange).flatten_verified("ETHUSDT", "SHORT", reason="RISK")
        self.assertEqual(exchange.close_calls, [("ETHUSDT", "SHORT", "RISK")])

    def test_first_attempt_still_open_second_attempt_flattens(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 1
        self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(len(exchange.close_calls), 2)
        self.assertIsNone(exchange.position)

    def test_exhausted_attempts_with_position_remaining_fails_closed(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 99
        with self.assertRaises(EmergencyFlattenError) as raised:
            self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_EXIT_FAILED_NOT_FLAT")
        self.assertIsNotNone(exchange.position)
        self.assertEqual(len(exchange.close_calls), 2)

    def test_close_exception_then_flat_snapshot_counts_as_success(self):
        exchange = FakeExchange()

        original = exchange.close_position

        def ambiguous(symbol, side, *, reason):
            # The exchange receives/executes the close but the response is lost.
            original(symbol, side, reason=reason)
            raise TimeoutError("response lost")

        exchange.close_position = ambiguous
        self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="AMBIGUOUS")
        self.assertIsNone(exchange.position)
        self.assertEqual(len(exchange.close_calls), 1)

    def test_close_exception_with_position_remaining_retries(self):
        exchange = FakeExchange()
        exchange.close_errors = [TimeoutError("timeout")]
        self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(len(exchange.close_calls), 2)
        self.assertIsNone(exchange.position)

    def test_snapshot_failure_after_first_attempt_retries(self):
        exchange = FakeExchange()
        # Initial snapshot succeeds; first post-close verify fails; second verify flat.
        exchange.snapshot_errors = [None, RuntimeError("verify unavailable")]
        self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(len(exchange.close_calls), 2)
        self.assertIsNone(exchange.position)

    def test_initial_snapshot_failure_does_not_block_close_attempt(self):
        exchange = FakeExchange()
        exchange.snapshot_errors = [RuntimeError("initial read unavailable")]
        self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(len(exchange.close_calls), 1)
        self.assertIsNone(exchange.position)

    def test_all_verification_reads_fail_means_flatness_unproven(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 99
        exchange.snapshot_errors = [RuntimeError("initial"), RuntimeError("v1"), RuntimeError("v2")]
        with self.assertRaises(EmergencyFlattenError) as raised:
            self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_EXIT_FAILED_NOT_FLAT")

    def test_initial_symbol_mismatch_fails_without_close(self):
        exchange = FakeExchange()
        exchange.position = ExchangePosition("ETHUSDT", "LONG", 1.0, 200.0)
        with self.assertRaises(EmergencyFlattenError) as raised:
            self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_POSITION_SYMBOL_MISMATCH")
        self.assertEqual(exchange.close_calls, [])

    def test_initial_side_mismatch_fails_without_close(self):
        exchange = FakeExchange()
        exchange.position = ExchangePosition("BTCUSDT", "SHORT", 0.1, 100.0)
        with self.assertRaises(EmergencyFlattenError) as raised:
            self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_POSITION_SIDE_MISMATCH")
        self.assertEqual(exchange.close_calls, [])

    def test_different_position_after_close_fails_closed(self):
        exchange = FakeExchange()
        exchange.after_close_position = ExchangePosition("ETHUSDT", "LONG", 1.0, 200.0)
        with self.assertRaises(EmergencyFlattenError) as raised:
            self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_POSITION_SYMBOL_MISMATCH")

    def test_different_side_after_close_fails_closed(self):
        exchange = FakeExchange()
        exchange.after_close_position = ExchangePosition("BTCUSDT", "SHORT", 0.1, 100.0)
        with self.assertRaises(EmergencyFlattenError) as raised:
            self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_POSITION_SIDE_MISMATCH")

    def test_configured_delay_runs_before_each_verification(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 1
        self.make(exchange, attempts=2, delay=0.25).flatten_verified(
            "BTCUSDT", "LONG", reason="RISK"
        )
        self.assertEqual(self.sleeps, [0.25, 0.25])

    def test_zero_delay_does_not_call_sleep(self):
        self.make(delay=0).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(self.sleeps, [])

    def test_sleep_failure_fails_closed(self):
        exchange = FakeExchange()
        emergency = EmergencyFlattener(
            exchange=exchange,
            config=EmergencyConfig(verify_delay_seconds=0.1),
            sleep=lambda _delay: (_ for _ in ()).throw(RuntimeError("sleep failed")),
        )
        with self.assertRaises(EmergencyFlattenError) as raised:
            emergency.flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(raised.exception.reason, "EMERGENCY_VERIFY_DELAY_FAILED")

    def test_reason_is_forwarded_exactly(self):
        exchange = FakeExchange()
        self.make(exchange).flatten_verified(
            "BTCUSDT", "LONG", reason="PROTECTIVE_STOP_RECOVERY_FAILED"
        )
        self.assertEqual(
            exchange.close_calls[0],
            ("BTCUSDT", "LONG", "PROTECTIVE_STOP_RECOVERY_FAILED"),
        )

    def test_max_attempts_one_is_honored(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 99
        with self.assertRaises(EmergencyFlattenError):
            self.make(exchange, attempts=1).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(len(exchange.close_calls), 1)

    def test_symbol_invalid_rejected_before_exchange_call(self):
        exchange = FakeExchange()
        with self.assertRaisesRegex(ValueError, "EMERGENCY_SYMBOL_INVALID"):
            self.make(exchange).flatten_verified("btc/usdt", "LONG", reason="RISK")
        self.assertEqual(exchange.snapshot_calls, 0)

    def test_symbol_whitespace_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_SYMBOL_INVALID"):
            self.make().flatten_verified(" BTCUSDT", "LONG", reason="RISK")

    def test_side_invalid_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_SIDE_INVALID"):
            self.make().flatten_verified("BTCUSDT", "BUY", reason="RISK")

    def test_reason_empty_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_REASON_INVALID"):
            self.make().flatten_verified("BTCUSDT", "LONG", reason="")

    def test_reason_whitespace_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_REASON_INVALID"):
            self.make().flatten_verified("BTCUSDT", "LONG", reason=" RISK")

    def test_reason_control_character_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_REASON_INVALID"):
            self.make().flatten_verified("BTCUSDT", "LONG", reason="RISK\nBAD")

    def test_reason_too_long_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMERGENCY_REASON_INVALID"):
            self.make().flatten_verified("BTCUSDT", "LONG", reason="X" * 201)

    def test_reentrant_emergency_call_is_rejected_not_silently_accepted(self):
        exchange = FakeExchange()
        emergency = self.make(exchange)
        seen = []

        def reenter():
            try:
                emergency.flatten_verified("BTCUSDT", "LONG", reason="NESTED")
            except EmergencyFlattenError as exc:
                seen.append(exc.reason)

        exchange.on_close = reenter
        emergency.flatten_verified("BTCUSDT", "LONG", reason="OUTER")
        self.assertEqual(seen, ["EMERGENCY_EXIT_ALREADY_IN_PROGRESS"])

    def test_lock_is_released_after_failed_emergency(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 99
        emergency = self.make(exchange, attempts=1)
        with self.assertRaises(EmergencyFlattenError):
            emergency.flatten_verified("BTCUSDT", "LONG", reason="FIRST")
        exchange.stay_open_attempts = 0
        emergency.flatten_verified("BTCUSDT", "LONG", reason="SECOND")
        self.assertIsNone(exchange.position)

    def test_flat_success_does_not_require_close_accounting(self):
        exchange = FakeExchange()

        def close_without_accounting(symbol, side, *, reason):
            exchange.close_calls.append((symbol, side, reason))
            exchange.position = None
            return None

        exchange.close_position = close_without_accounting
        self.make(exchange).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertIsNone(exchange.position)

    def test_close_result_does_not_replace_flatness_verification(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 99
        with self.assertRaises(EmergencyFlattenError):
            self.make(exchange, attempts=1).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        # FakeExchange returned a CloseFill, but exchange truth remained OPEN.
        self.assertIsNotNone(exchange.position)

    def test_close_is_retried_only_after_proven_remaining_exposure(self):
        exchange = FakeExchange()
        exchange.stay_open_attempts = 1
        self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(exchange.snapshot_calls, 3)  # initial + one per attempt

    def test_ambiguous_first_close_that_actually_flattens_is_not_retried(self):
        exchange = FakeExchange()

        def ambiguous(symbol, side, *, reason):
            exchange.close_calls.append((symbol, side, reason))
            exchange.position = None
            raise TimeoutError("lost ack")

        exchange.close_position = ambiguous
        self.make(exchange, attempts=2).flatten_verified("BTCUSDT", "LONG", reason="RISK")
        self.assertEqual(len(exchange.close_calls), 1)


if __name__ == "__main__":
    unittest.main()
