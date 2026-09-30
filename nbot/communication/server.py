"""Authenticated bounded HTTP(S) service for the Observation control plane."""

from __future__ import annotations

import json
from pathlib import Path
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping

from .auth import authorized, validate_control_token
from .contracts import ExecutionOutcome, TradeRequest
from .validation import ProtocolValidationError, canonical_json


_MAX_BODY_BYTES = 1_048_576
_REQUEST_IO_TIMEOUT_SECONDS = 5.0
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ObservationControlServer:
    def __init__(
        self,
        *,
        target: Any,
        auth_token: str,
        host: str = "127.0.0.1",
        port: int = 8765,
        tls_certfile: str | Path | None = None,
        tls_keyfile: str | Path | None = None,
        operator_status_provider: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.target = target
        self.auth_token = validate_control_token(auth_token)
        self.host = str(host).strip()
        if not self.host:
            raise ValueError("NBOT_CONTROL_HOST_INVALID")
        self.port = int(port)
        if not (0 <= self.port <= 65535):
            raise ValueError("NBOT_CONTROL_PORT_INVALID")
        self.tls_certfile = None if tls_certfile is None else Path(tls_certfile)
        self.tls_keyfile = None if tls_keyfile is None else Path(tls_keyfile)
        self.operator_status_provider = operator_status_provider
        if (self.tls_certfile is None) != (self.tls_keyfile is None):
            raise ValueError("NBOT_CONTROL_TLS_CERT_KEY_PAIR_REQUIRED")
        if self.host not in _LOOPBACK_HOSTS and self.tls_certfile is None:
            raise ValueError("NBOT_CONTROL_TLS_REQUIRED_FOR_NON_LOOPBACK")
        if self.tls_certfile is not None:
            if not self.tls_certfile.is_file() or not self.tls_keyfile or not self.tls_keyfile.is_file():
                raise ValueError("NBOT_CONTROL_TLS_FILE_MISSING")
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int] | None:
        if self._server is None:
            return None
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> tuple[str, int]:
        if self._server is not None:
            raise RuntimeError("NBOT_CONTROL_SERVER_ALREADY_STARTED")
        outer = self
        target = self.target

        class Handler(BaseHTTPRequestHandler):
            server_version = "NBOTV3ObservationControl/1"

            def setup(self):
                super().setup()
                # A peer that advertises a body and then stops sending must not
                # occupy a control handler indefinitely.
                self.connection.settimeout(_REQUEST_IO_TIMEOUT_SECONDS)

            def log_message(self, _format, *_args):
                return

            def _authorized(self) -> bool:
                return authorized(
                    token=outer.auth_token,
                    authorization_header=self.headers.get("Authorization"),
                )

            def do_GET(self):
                if not self._authorized():
                    self._send(401, {"error": "AUTHENTICATION_FAILED"})
                    return
                if self.path != "/health":
                    self._send(404, {"error": "NOT_FOUND"})
                    return
                try:
                    self._send(200, target.health_snapshot())
                except Exception:
                    self._send(500, {"error": "INTERNAL_ERROR"})

            def do_POST(self):
                if not self._authorized():
                    self._send(401, {"error": "AUTHENTICATION_FAILED"})
                    return
                try:
                    payload = self._read_json()
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
                    if self.path == "/operator-status":
                        if outer.operator_status_provider is None:
                            self._send(503, {"error": "OPERATOR_STATUS_UNAVAILABLE"})
                            return
                        if set(payload) != {"view"} or not isinstance(payload.get("view"), str):
                            raise ValueError("OBSERVATION_OPERATOR_STATUS_REQUEST_INVALID")
                        result = dict(outer.operator_status_provider(str(payload["view"])))
                        if result.get("order_authority") != "NONE":
                            raise ValueError("OBSERVATION_OPERATOR_STATUS_AUTHORITY_INVALID")
                        self._send(200, result)
                        return
                    self._send(404, {"error": "NOT_FOUND"})
                except (ProtocolValidationError, TypeError, ValueError) as exc:
                    self._send(
                        400,
                        {"error": type(exc).__name__, "detail": str(exc)},
                    )
                except Exception as exc:
                    # Keep detailed server-side invariant names out of the wire
                    # response; callers only need fail-closed behavior.
                    self._send(
                        409 if exc.__class__.__name__ == "ObservationControlError" else 500,
                        {"error": exc.__class__.__name__},
                    )

            def _read_json(self) -> dict[str, Any]:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise ValueError("NBOT_CONTROL_CONTENT_LENGTH_INVALID") from exc
                if length <= 0 or length > _MAX_BODY_BYTES:
                    raise ValueError("NBOT_CONTROL_BODY_SIZE_INVALID")
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("NBOT_CONTROL_JSON_INVALID") from exc
                if not isinstance(payload, dict):
                    raise ValueError("NBOT_CONTROL_JSON_OBJECT_REQUIRED")
                return payload

            def _send(self, status: int, payload: dict[str, Any]) -> None:
                body = canonical_json(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        context = None
        if self.tls_certfile is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(str(self.tls_certfile), str(self.tls_keyfile))

        class ControlHTTPServer(ThreadingHTTPServer):
            # Individual request sockets are bounded above, and daemon request
            # threads ensure process shutdown never waits on a broken peer.
            daemon_threads = True
            slots = threading.BoundedSemaphore(32)

            def process_request(self, request, client_address):
                if not self.slots.acquire(blocking=False):
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, client_address)
                except BaseException:
                    self.slots.release()
                    raise

            def process_request_thread(self, request, client_address):
                try:
                    request.settimeout(_REQUEST_IO_TIMEOUT_SECONDS)
                    if context is not None:
                        # Handshake in the bounded worker, never the accept loop.
                        request = context.wrap_socket(request, server_side=True)
                    super().process_request_thread(request, client_address)
                except (OSError, ssl.SSLError):
                    self.shutdown_request(request)
                finally:
                    self.slots.release()

        server = ControlHTTPServer((self.host, self.port), Handler)
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="nbot-observation-control-api",
            daemon=True,
        )
        self._thread.start()
        assert self.address is not None
        return self.address

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
