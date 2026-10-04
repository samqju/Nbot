import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from nbot.operator.execution import ExecutionOperatorSurface
from nbot.operator.telegram import TelegramClient, TelegramConfig
from nbot.operator.status_proxy import _format_learning
from tests.test_v386_operator_observability import FakeWorker
from tests.test_v397_operator_research_visibility import CaptureDispatcher

class SimpleTelegramTests(unittest.TestCase):
    def surface(self, root, *, separate=False, reader=None):
        config = TelegramConfig("token", "-100123", "456", 1., "456" if separate else "")
        client = TelegramClient(config, requester=lambda *_: {"ok": True, "result": []})
        return ExecutionOperatorSurface(
            repo_root=Path(root), profile="live-paper", worker=FakeWorker(),
            telegram=client, system_log=logging.getLogger("simple"),
            trade_log=logging.getLogger("simple.trade"), enable_policy=lambda: (False, "BLOCKED"),
            observation_status_reader=reader)

    def test_removed_commands_do_not_query_or_change_state(self):
        with tempfile.TemporaryDirectory() as td:
            reader = Mock()
            s = self.surface(td, reader=reader)
            s.dispatcher = CaptureDispatcher()
            for cmd in ["health","observation","recommendation","memory","epoch","champion",
                        "challenger","governance","research","paper","db"]:
                s.handle_command("/"+cmd)
            self.assertEqual(len(s.dispatcher.warning), 11)
            reader.assert_not_called()
            self.assertEqual(s.worker.enable_calls+s.worker.disable_calls, 0)

    def test_private_commands_authorize_user_and_chat_and_reply_privately(self):
        with tempfile.TemporaryDirectory() as td:
            s = self.surface(td, separate=True)
            calls = []
            s.telegram._requester = lambda method, payload, timeout: calls.append(dict(payload)) or {"ok":True,"result":{"message_id":1}}
            s._listener.client._requester = s.telegram._requester
            self.assertEqual(s.dispatcher.client.config.chat_id, "-100123")
            self.assertEqual(s.command_dispatcher.client.config.chat_id, "456")
            # Same user in the channel, or another user in the private chat, cannot act.
            for i, (chat, user) in enumerate([(-100123,456),(456,999)]):
                s._listener._dispatch({"update_id":i,"message":{"chat":{"id":chat},"from":{"id":user},"text":"/disable"}})
            self.assertEqual(s.worker.disable_calls, 0)
            s._listener._dispatch({"update_id":3,"message":{"chat":{"id":456},"from":{"id":456},"text":"/disable"}})
            self.assertEqual(s.worker.disable_calls, 1)
            s.command_dispatcher.stop()
            self.assertTrue(calls)
            self.assertTrue(all(p["chat_id"]=="456" for p in calls))

    def test_status_explains_remote_wait_without_mutating_worker(self):
        reader = Mock(return_value={"order_authority":"NONE","document":{
            "status":"NOT_READY","reason":"LEARNED_LIVE_EVENT_STALE_OR_FUTURE"}})
        with tempfile.TemporaryDirectory() as td:
            s=self.surface(td,reader=reader)
            body=s._status_body()
            self.assertIn("Learning service: not ready",body)
            self.assertIn("stale or future",body)
            self.assertEqual(s.worker.enable_calls+s.worker.disable_calls,0)
            reader.side_effect=RuntimeError("offline")
            self.assertIn("status unavailable",s._status_body())

    def test_command_chat_env_is_optional_and_separate(self):
        base={"EXECUTION_TELEGRAM_BOT_TOKEN":"token","EXECUTION_TELEGRAM_CHAT_ID":"-100123",
              "EXECUTION_TELEGRAM_OPERATOR_USER_ID":"456"}
        self.assertEqual(TelegramConfig.from_environment(base,prefix="EXECUTION").command_chat_id,"")
        base["EXECUTION_TELEGRAM_COMMAND_CHAT_ID"]="456"
        cfg=TelegramConfig.from_environment(base,prefix="EXECUTION")
        self.assertEqual(cfg.command_chat_id,"456")
        self.assertEqual(cfg.chat_id,"-100123")

    def test_learning_does_not_claim_profit_improvement(self):
        body=_format_learning({"challengers":{"passed_windows":2,"rejected_windows":3,
            "active_future_evidence":{"available_future_events":4,"required_future_events":40}}})
        self.assertIn("Tests passed: 2",body)
        self.assertIn("Tests rejected: 3",body)
        self.assertIn("4 / 40",body)
        self.assertIn("do not prove",body)
