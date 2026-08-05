import json
import os
import unittest
from unittest.mock import Mock, patch

import websocket

from execution.live_user_stream import LiveUserStream


class Response:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self._data


class Log:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def error(self, message):
        self.errors.append(message)


class Socket:
    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.closed = False
        self.pings = 0
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self):
        if self.messages:
            item = self.messages.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        raise websocket.WebSocketTimeoutException("idle")

    def ping(self):
        self.pings += 1

    def close(self):
        self.closed = True


class Phase23LiveUserStreamTests(unittest.TestCase):
    def _stream(self, *, socket=None):
        session = Mock()
        session.post.return_value = Response({"listenKey": "abc"})
        session.put.return_value = Response({})
        session.delete.return_value = Response({})
        log = Log()
        env = {
            "LIVE_USER_STREAM_READY_TIMEOUT": "2",
            "LIVE_USER_STREAM_KEEPALIVE_SECONDS": "60",
            "LIVE_USER_STREAM_RECONNECT_SECONDS": "1",
            "LIVE_USER_STREAM_RECV_TIMEOUT_SECONDS": "5",
            "LIVE_USER_STREAM_EVENT_QUEUE_MAX": "10",
        }
        with patch.dict(os.environ, env, clear=False):
            stream = LiveUserStream(
                system_log=log,
                session=session,
                base_url="https://fapi.binance.com",
                user_ws_url="wss://fstream.binance.com/ws",
                websocket_factory=lambda *args, **kwargs: socket or Socket(),
                sleep_fn=lambda seconds: None,
            )
        return stream, session, log

    def test_listen_key_create_keepalive_and_close_use_only_stream_endpoints(self):
        stream, session, _ = self._stream()
        key = stream._create_listen_key()
        self.assertEqual(key, "abc")
        stream._keepalive_listen_key(key)
        stream._close_listen_key(key)
        self.assertIn("/fapi/v1/listenKey", session.post.call_args.args[0])
        self.assertIn("/fapi/v1/listenKey", session.put.call_args.args[0])
        self.assertIn("/fapi/v1/listenKey", session.delete.call_args.args[0])

    def test_event_queue_is_bounded_and_drainable(self):
        stream, _, _ = self._stream()
        for idx in range(12):
            stream._record_event({"e": "ACCOUNT_UPDATE", "i": idx})
        events = stream.drain_events()
        self.assertEqual(len(events), 10)
        self.assertEqual(events[0]["i"], 2)
        self.assertEqual(events[-1]["i"], 11)
        self.assertEqual(stream.drain_events(), [])

    def test_wait_ready_and_health_reflect_stream_state(self):
        stream, _, _ = self._stream()
        self.assertFalse(stream.is_healthy())
        stream._healthy = True
        stream._ready.set()
        self.assertTrue(stream.wait_ready(0))
        self.assertTrue(stream.is_healthy())
        stream._stop.set()
        self.assertFalse(stream.is_healthy())

    def test_timeout_pings_idle_socket_without_marking_event(self):
        socket = Socket([websocket.WebSocketTimeoutException("idle")])
        stream, _, _ = self._stream(socket=socket)
        stream._stop.set()
        with self.assertRaises(websocket.WebSocketTimeoutException):
            socket.recv()
        socket.ping()
        self.assertEqual(socket.pings, 1)
        self.assertIsNone(stream.last_event_timestamp_ms())

    def test_json_event_is_recorded(self):
        stream, _, _ = self._stream()
        event = json.loads('{"e":"ACCOUNT_UPDATE","E":123}')
        stream._record_event(event)
        self.assertEqual(stream.drain_events(), [event])
        self.assertIsNotNone(stream.last_event_timestamp_ms())

    def test_intentional_shutdown_is_not_logged_as_reconnect_error(self):
        stream, _, log = self._stream()
        stream._stop.set()
        stream._healthy = True
        stream._ready.set()
        stream._run()
        self.assertFalse(
            any("LIVE_USER_STREAM_RECONNECTING" in x for x in log.errors)
        )

    def test_invalid_user_websocket_url_is_rejected(self):
        session = Mock()
        env = {
            "LIVE_USER_STREAM_READY_TIMEOUT": "20",
            "LIVE_USER_STREAM_KEEPALIVE_SECONDS": "1800",
            "LIVE_USER_STREAM_RECONNECT_SECONDS": "5",
            "LIVE_USER_STREAM_RECV_TIMEOUT_SECONDS": "60",
            "LIVE_USER_STREAM_EVENT_QUEUE_MAX": "1000",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "LIVE_USER_WS_URL_INVALID"):
                LiveUserStream(
                    system_log=Log(),
                    session=session,
                    base_url="https://fapi.binance.com",
                    user_ws_url="http://invalid",
                )


if __name__ == "__main__":
    unittest.main()
