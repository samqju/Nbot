import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nbot.runtime_ops import TelegramConfig, TelegramOperator, configure_role_logging


class RuntimeOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        trade = logging.getLogger("nbot.v2.execution.trade")
        for handler in list(trade.handlers):
            trade.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        root.addHandler(logging.NullHandler())
        self.tmp.cleanup()

    @staticmethod
    def _flush_all():
        for logger in (logging.getLogger(), logging.getLogger("nbot.v2.execution.trade")):
            for handler in logger.handlers:
                try:
                    handler.flush()
                except Exception:
                    pass

    def test_execution_and_observation_write_separate_rotating_logs(self):
        execution_path = self.root / "execution.log"
        trades_path = self.root / "execution-trades.log"
        observation_path = self.root / "observation.log"

        execution, trades = configure_role_logging(
            "EXECUTION", log_path=execution_path, trade_log_path=trades_path, stderr=False,
        )
        execution.info("EXECUTION_ONLY_EVENT proposal_id=P1")
        trades.info("TRADE_ONLY_EVENT outcome_id=O1")
        self._flush_all()

        self.assertIn("EXECUTION_ONLY_EVENT", execution_path.read_text())
        self.assertNotIn("TRADE_ONLY_EVENT", execution_path.read_text())
        self.assertIn("TRADE_ONLY_EVENT", trades_path.read_text())

        observation, _ = configure_role_logging(
            "OBSERVATION", log_path=observation_path, stderr=False,
        )
        observation.info("OBSERVATION_ONLY_EVENT market_event_id=M1")
        self._flush_all()
        self.assertIn("OBSERVATION_ONLY_EVENT", observation_path.read_text())
        self.assertNotIn("OBSERVATION_ONLY_EVENT", execution_path.read_text())
        self.assertNotIn("EXECUTION_ONLY_EVENT", observation_path.read_text())

    def test_log_rotation_defaults_match_v1_parity(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            path = self.root / "execution.log"
            configure_role_logging("EXECUTION", log_path=path, stderr=False)
            handler = next(h for h in logging.getLogger().handlers if hasattr(h, "maxBytes"))
            self.assertEqual(handler.maxBytes, 5 * 1024 * 1024)
            self.assertEqual(handler.backupCount, 3)

    def test_execution_can_use_legacy_telegram_env_but_observation_cannot_share_long_poll_bot(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "legacy-token",
            "TELEGRAM_CHAT_ID": "123",
            "TELEGRAM_OPERATOR_USER_ID": "456",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            execution = TelegramConfig.from_env("EXECUTION")
            observation = TelegramConfig.from_env("OBSERVATION")
        self.assertIsNotNone(execution)
        self.assertEqual(execution.bot_token, "legacy-token")
        self.assertIsNone(observation)

    def test_observation_telegram_requires_role_specific_credentials(self):
        env = {
            "OBSERVATION_TELEGRAM_BOT_TOKEN": "observer-token",
            "OBSERVATION_TELEGRAM_CHAT_ID": "789",
            "OBSERVATION_TELEGRAM_OPERATOR_USER_ID": "456",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = TelegramConfig.from_env("OBSERVATION")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.role, "OBSERVATION")
        self.assertEqual(cfg.bot_token, "observer-token")

    def test_telegram_send_failure_never_raises_into_worker(self):
        logger = logging.getLogger("runtime-ops-test")
        logger.handlers = [logging.NullHandler()]
        cfg = TelegramConfig("token", "chat", "operator", "EXECUTION", api_timeout_seconds=0.1)
        operator = TelegramOperator(cfg, logger)
        with mock.patch("nbot.runtime_ops.requests.post", side_effect=RuntimeError("network down")):
            operator.critical("TEST", "capital path must continue")


if __name__ == "__main__":
    unittest.main()
