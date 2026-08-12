"""Local HTTP boundary for the Observation Worker.

The server remains loopback-only during local hardening. Optional bearer
authentication is supported so failure behavior can be proven before cross-VPS
exposure; TLS and non-loopback binding remain a deployment step.
"""

from __future__ import annotations

import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from communication.execution_outcome import ExecutionOutcome
from communication.protocol import ProtocolValidationError
from communication.trade_request import TradeRequest


_MAX_BODY_BYTES = 1_048_576


class ObservationHTTPServer:
    def __init__(
        self,
        *,
        target,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_token: str | None = None,
        system_log=None,
    ):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("OBSERVATION_LOCAL_API_MUST_BIND_LOOPBACK")
        self.target = target
        self.host = host
        self.port = int(port)
        if not (0 <= self.port <= 65535):
            raise ValueError("OBSERVATION_API_PORT_INVALID")
        token = str(auth_token or "").strip()
        self.auth_token = token or None
        self.system_log = system_log
        self._server = None
        self._thread = None

    @property
    def address(self):
        if self._server is None:
            return None
        return self._server.server_address

    def start(self) -> tuple[str, int]:
        if self._server is not None:
            raise RuntimeError("OBSERVATION_HTTP_SERVER_ALREADY_STARTED")
        target = self.target
        outer = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "NBOTObservation/1"

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                if self.path != "/health":
                    self._send(404, {"error": "NOT_FOUND"})
                    return
                ready, reason = target.recommendation_store.readiness()
                payload = {
                    "status": "READY" if ready else "NOT_READY",
                    "reason": reason,
                    "order_authority": "NONE",
                }
                health_getter = getattr(
                    target,
                    "observation_health_snapshot",
                    None,
                )
                if callable(health_getter):
                    payload["health"] = health_getter()
                self._send(200, payload)

            def do_POST(self):
                if not outer._is_authorized(
                    self.headers.get("Authorization")
                ):
                    outer._log(
                        "warning",
                        "OBSERVATION_HTTP_AUTHENTICATION_FAILED | "
                        f"path={self.path}",
                    )
                    self._send(401, {"error": "AUTHENTICATION_FAILED"})
                    return
                try:
                    payload = self._read_json()
                    if self.path == "/learning-status":
                        if payload not in ({}, {"request": "LEARNING_STATUS"}):
                            raise ValueError(
                                "OBSERVATION_LEARNING_STATUS_REQUEST_INVALID"
                            )
                        getter = getattr(
                            target,
                            "learning_operator_status",
                            None,
                        )
                        if not callable(getter):
                            self._send(503, {
                                "error": "LEARNING_STATUS_UNAVAILABLE"
                            })
                            return
                        self._send(200, getter())
                        return
                    if self.path == "/trade-request":
                        request = TradeRequest.from_dict(payload)
                        response = target.handle_trade_request(request)
                        self._send(200, response.to_dict())
                        return
                    if self.path == "/execution-outcome":
                        outcome = ExecutionOutcome.from_dict(payload)
                        acknowledgement = target.receive_execution_outcome(outcome)
                        self._send(200, acknowledgement.to_dict())
                        return
                    self._send(404, {"error": "NOT_FOUND"})
                except (ProtocolValidationError, TypeError, ValueError) as exc:
                    self._send(
                        400,
                        {
                            "error": type(exc).__name__,
                            "detail": str(exc),
                        },
                    )
                except Exception as exc:
                    outer._log(
                        "error",
                        "OBSERVATION_HTTP_REQUEST_FAILED | "
                        f"path={self.path} | error={type(exc).__name__}:{exc}",
                    )
                    self._send(500, {"error": "INTERNAL_ERROR"})

            def _read_json(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise ValueError("OBSERVATION_HTTP_CONTENT_LENGTH_INVALID") from exc
                if length <= 0 or length > _MAX_BODY_BYTES:
                    raise ValueError("OBSERVATION_HTTP_BODY_SIZE_INVALID")
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("OBSERVATION_HTTP_JSON_INVALID") from exc
                if not isinstance(payload, dict):
                    raise ValueError("OBSERVATION_HTTP_JSON_OBJECT_REQUIRED")
                return payload

            def _send(self, status: int, payload: dict):
                body = json.dumps(
                    payload,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="nbot-observation-api",
            daemon=True,
        )
        self._thread.start()
        host, port = self._server.server_address[:2]
        self._log(
            "info",
            "OBSERVATION_HTTP_SERVER_STARTED | "
            f"host={host} | port={port} | scope=LOOPBACK_ONLY | "
            f"auth={'REQUIRED' if self.auth_token else 'DISABLED'}",
        )
        return str(host), int(port)

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)
        self._log("info", "OBSERVATION_HTTP_SERVER_STOPPED")

    def _is_authorized(self, authorization: str | None) -> bool:
        if self.auth_token is None:
            return True
        expected = f"Bearer {self.auth_token}"
        return hmac.compare_digest(str(authorization or ""), expected)

    def _log(self, level: str, message: str) -> None:
        if self.system_log is None:
            return
        getattr(self.system_log, level, lambda *_args, **_kwargs: None)(message)
