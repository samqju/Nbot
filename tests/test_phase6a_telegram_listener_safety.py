import unittest
from unittest.mock import Mock, patch

import utils.telegram_notifier as notifier


class Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TelegramListenerSafetyTests(unittest.TestCase):
    def setUp(self):
        notifier._CONFIGURED = True
        notifier._TELEGRAM_BOT_TOKEN = "token"
        notifier._TELEGRAM_CHAT_ID = "chat"
        notifier.AUTHORIZED_USER_ID = "123"
        notifier._LAST_UPDATE_ID = None
        notifier._LISTENER_STARTED = False

    def tearDown(self):
        notifier._LISTENER_STARTED = False
        notifier._LAST_UPDATE_ID = None

    def test_listener_discards_offline_backlog_and_starts_only_once(self):
        fake_thread = Mock()
        fake_thread.start = Mock()

        get_responses = [
            Response(
                {
                    "result": [
                        {
                            "update_id": 77,
                            "message": {
                                "from": {"id": 123},
                                "text": "/enable",
                            },
                        }
                    ]
                }
            )
        ]

        callback = Mock()
        with patch(
            "utils.telegram_notifier.requests.get",
            side_effect=get_responses,
        ), patch(
            "utils.telegram_notifier.threading.Thread",
            return_value=fake_thread,
        ) as thread_cls:
            self.assertTrue(notifier.start_operator_listener(callback))
            self.assertFalse(notifier.start_operator_listener(callback))

        callback.assert_not_called()
        self.assertEqual(notifier._LAST_UPDATE_ID, 77)
        thread_cls.assert_called_once()
        fake_thread.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
