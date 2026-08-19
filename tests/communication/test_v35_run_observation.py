from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[2]


def load_module():
    spec = importlib.util.spec_from_file_location("v35_run_observation", REPO / "run_observation.py")
    if spec is None or spec.loader is None:
        raise AssertionError("run_observation spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeLock:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class FakeWorker:
    def __init__(self):
        self.database = object()
        self.runs = []
        self.stop_calls = 0

    def run(self, *, max_cycles=None):
        self.runs.append(max_cycles)
        return 1

    def stop(self):
        self.stop_calls += 1


class FakeSupervisor:
    def __init__(self, target, *, refresh_seconds):
        self.target = target
        self.refresh_seconds = refresh_seconds
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


class FakeServer:
    last = None

    def __init__(self, **kwargs):
        type(self).last = self
        self.kwargs = kwargs
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1
        return "127.0.0.1", 8765

    def stop(self):
        self.stopped += 1


class V35RunObservationTests(unittest.TestCase):
    def test_control_api_requires_auth_token(self):
        module = load_module()
        worker = FakeWorker()
        with mock.patch.object(module, "build_observation_worker", return_value=(worker, FakeLock())), \
             mock.patch.object(module.signal, "signal"), \
             mock.patch.dict(module.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "CONTROL_AUTH_TOKEN_REQUIRED"):
                module.main(["--profile", "testnet-trade", "--once", "--control-api"])
        self.assertEqual(worker.runs, [])

    def test_control_api_lifecycle_is_bounded_by_observation_lock(self):
        module = load_module()
        worker = FakeWorker()
        fake_target = object()
        supervisors = []

        def supervisor_factory(target, *, refresh_seconds):
            item = FakeSupervisor(target, refresh_seconds=refresh_seconds)
            supervisors.append(item)
            return item

        with mock.patch.object(module, "build_observation_worker", return_value=(worker, FakeLock())), \
             mock.patch.object(module, "ObservationControlTarget", return_value=fake_target) as target_ctor, \
             mock.patch.object(module, "RecommendationSupervisor", side_effect=supervisor_factory), \
             mock.patch.object(module, "ObservationControlServer", FakeServer), \
             mock.patch.object(module, "_git_sha", return_value="a" * 40), \
             mock.patch.object(module.signal, "signal"), \
             mock.patch.object(module, "_emit"), \
             mock.patch.dict(module.os.environ, {"NBOT_CONTROL_AUTH_TOKEN": "x" * 40}, clear=True):
            rc = module.main(["--profile", "testnet-trade", "--once", "--control-api"])
        self.assertEqual(rc, 0)
        self.assertEqual(worker.runs, [1])
        target_ctor.assert_called_once()
        self.assertEqual(supervisors[0].started, 1)
        self.assertEqual(supervisors[0].stopped, 1)
        self.assertIsNotNone(FakeServer.last)
        self.assertEqual(FakeServer.last.started, 1)
        self.assertEqual(FakeServer.last.stopped, 1)
        self.assertEqual(FakeServer.last.kwargs["auth_token"], "x" * 40)

    def test_v35_observation_surface_has_no_execution_or_exchange_import(self):
        for rel in (
            "nbot/observation/recommendation.py",
            "nbot/communication/server.py",
            "run_observation.py",
        ):
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertNotIn("nbot.execution", text)
            self.assertNotIn("nbot.exchange", text)
        contracts = (REPO / "nbot/communication/contracts.py").read_text(encoding="utf-8")
        self.assertNotIn("nbot.execution", contracts)
        self.assertNotIn("nbot.observation", contracts)
        self.assertNotIn("nbot.config", contracts)
