from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nbot.communication.client import ObservationClientError, probe_observation_health
from nbot.communication.validation import PROTOCOL_VERSION
from nbot.config.profiles import get_profile
from nbot.config.validation import (
    validate_local_protocol_contract_v39,
    validate_observation_database_v39,
)
from nbot.observation.config import OBSERVATION_SCHEMA_VERSION


REPO = Path(__file__).resolve().parents[1]


def _make_observation_db(root: Path, profile_name: str, *, environment: str | None = None) -> Path:
    profile = get_profile(profile_name)
    path = root / profile.observation_db
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE child("
            "id INTEGER PRIMARY KEY,"
            "parent_id INTEGER REFERENCES parent(id)"
            ")"
        )
        rows = {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "role": "OBSERVATION",
            "market_environment": environment or profile.market_environment,
        }
        conn.executemany(
            "INSERT INTO metadata(key,value) VALUES (?,?)",
            sorted(rows.items()),
        )
        conn.commit()
    finally:
        conn.close()
    return path


class _HealthHandler(BaseHTTPRequestHandler):
    payload: dict[str, object] = {}
    expected_auth: str = ""

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("Authorization") != self.expected_auth:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}')
            return
        encoded = json.dumps(self.payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class V39PreV310DoctorMaturityTests(unittest.TestCase):
    def test_observation_database_integrity_passes_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _make_observation_db(root, "live-paper")
            before = path.stat().st_mtime_ns
            result = validate_observation_database_v39(
                repo_root=root,
                profile=get_profile("live-paper"),
            )
            after = path.stat().st_mtime_ns

            self.assertTrue(result.ok, result.warnings)
            self.assertEqual(before, after)
            self.assertIn("OBSERVATION_DATABASE_INTEGRITY_OK", result.checks)
            self.assertIn("OBSERVATION_DATABASE_FOREIGN_KEYS_OK", result.checks)
            self.assertIn("OBSERVATION_DATABASE_LINEAGE_METADATA_OK", result.checks)

    def test_observation_database_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_observation_database_v39(
                repo_root=tmp,
                profile=get_profile("live-paper"),
            )
            self.assertFalse(result.ok)
            self.assertIn(
                "OBSERVATION_DATABASE_MISSING:data/observation/live/observer.db",
                result.warnings,
            )

    def test_observation_database_wrong_environment_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_observation_db(root, "live-paper", environment="TESTNET")
            result = validate_observation_database_v39(
                repo_root=root,
                profile=get_profile("live-paper"),
            )
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    item.startswith(
                        "OBSERVATION_DATABASE_METADATA_MISMATCH:"
                        "market_environment:TESTNET:LIVE"
                    )
                    for item in result.warnings
                )
            )

    def test_local_protocol_profile_contract_matches_all_profiles(self):
        for name in ("testnet-trade", "live-paper", "live-trade"):
            result = validate_local_protocol_contract_v39(
                profile=get_profile(name)
            )
            self.assertTrue(result.ok, (name, result.warnings))
            self.assertIn(
                f"CONTROL_PROTOCOL_VERSION:{PROTOCOL_VERSION}",
                result.checks,
            )
            self.assertIn(
                "CONTROL_PROFILE_CONTRACT_LOCAL_MATCH",
                result.checks,
            )

    def test_health_probe_is_read_only_and_authenticated(self):
        token = "a" * 64
        _HealthHandler.expected_auth = f"Bearer {token}"
        _HealthHandler.payload = {
            "status": "READY",
            "protocol_version": PROTOCOL_VERSION,
            "profile": "live-paper",
            "market_environment": "LIVE",
            "evidence_lineage": "LIVE_PAPER_OPERATIONAL",
            "release_sha": "b" * 40,
            "order_authority": "NONE",
        }
        server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = probe_observation_health(
                base_url=f"http://127.0.0.1:{server.server_port}",
                auth_token=token,
                timeout_seconds=2.0,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2.0)

        self.assertEqual(payload["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(payload["order_authority"], "NONE")

    def test_health_probe_rejects_order_authority(self):
        token = "c" * 64
        _HealthHandler.expected_auth = f"Bearer {token}"
        _HealthHandler.payload = {
            "status": "READY",
            "order_authority": "BINANCE_ORDER_WRITE",
        }
        server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaisesRegex(
                ObservationClientError,
                "OBSERVATION_HEALTH_ORDER_AUTHORITY_INVALID",
            ):
                probe_observation_health(
                    base_url=f"http://127.0.0.1:{server.server_port}",
                    auth_token=token,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2.0)

    def test_execution_start_excludes_remote_observation_dependency(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        self.assertIn(
            "_doctor_payload(profile_name, include_remote_compatibility=False)",
            text,
        )
        self.assertIn(
            "def _doctor_payload(\n"
            "    profile_name: str,\n"
            "    *,\n"
            "    include_remote_compatibility: bool = True,",
            text,
        )

    def test_gap_ledger_marks_doctor_and_cluster_maturity_closed(self):
        text = (
            REPO / "docs/PRE_V310_GAP_LEDGER.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "[x] Integrate real Observation database integrity",
            text,
        )
        self.assertIn(
            "[x] Integrate local protocol/profile contract validation",
            text,
        )
        self.assertIn(
            "[x] Implement `nbotctl cluster doctor/start/stop/status`",
            text,
        )


if __name__ == "__main__":
    unittest.main()
