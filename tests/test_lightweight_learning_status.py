"""Reporting must not decompress archives or start parallel report builders."""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from nbot.observation.research_memory import ResearchMemoryStore
from nbot.operator.status_proxy import ObservationReadOnlyStatusProvider


class LightweightLearningStatusTests(unittest.TestCase):
    def test_timestamp_count_preserves_strict_horizon_spacing_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ResearchMemoryStore(Path(directory) / "memory.db")
            # Deliberately no payload columns: reporting may only read timestamps.
            with sqlite3.connect(memory.path) as conn:
                conn.execute("CREATE TABLE research_memory_events(event_open_ms INTEGER PRIMARY KEY)")
                conn.executemany("INSERT INTO research_memory_events VALUES (?)",
                                 [(x,) for x in (10, 11, 12, 21, 22, 23, 32, 33, 44)])
            self.assertEqual(memory.count_event_slots(after_event_ms=10, spacing_ms=10, limit=40), 4)
            self.assertEqual(memory.count_event_slots(after_event_ms=10, spacing_ms=10, limit=2), 2)
            self.assertEqual(memory.count_event_slots(after_event_ms=44, spacing_ms=10, limit=40), 0)
            self.assertEqual(memory.count_event_slots(after_event_ms=10, spacing_ms=10, limit=0), 0)
            with self.assertRaises(ValueError):
                memory.count_event_slots(after_event_ms=10, spacing_ms=10, limit=1001)

    def test_count_does_not_create_a_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ResearchMemoryStore(Path(directory) / "missing.db")
            with self.assertRaises(sqlite3.OperationalError):
                memory.count_event_slots(after_event_ms=0, spacing_ms=1, limit=40)
            self.assertFalse(memory.path.exists())

    def test_learning_cache_expires_and_cannot_be_mutated_by_caller(self):
        provider = ObservationReadOnlyStatusProvider(repo_root=Path('.'), target=object())
        clock = [100.0]
        report = {'telegram_body': 'progress', 'document': {'count': 1}}
        with patch('nbot.operator.status_proxy.time.monotonic', side_effect=lambda: clock[0]), \
                patch.object(provider, '_status_document', return_value=report) as build:
            first = provider.status('learning')
            first['document']['count'] = 999
            self.assertEqual(provider.status('learning')['document']['count'], 1)
            self.assertEqual(build.call_count, 1)
            clock[0] = 130.0
            provider.status('learning')
            self.assertEqual(build.call_count, 2)

    def test_concurrent_request_does_not_launch_a_second_builder(self):
        provider = ObservationReadOnlyStatusProvider(repo_root=Path('.'), target=object())
        started, release = threading.Event(), threading.Event()
        results = []
        def build(view):
            started.set()
            release.wait(3)
            return {'telegram_body': 'progress', 'document': {}}
        with patch.object(provider, '_status_document', side_effect=build) as builder:
            worker = threading.Thread(target=lambda: results.append(provider.status('learning')))
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                with self.assertRaisesRegex(RuntimeError, 'LEARNING_REPORT_BUSY'):
                    provider.status('learning')
                self.assertEqual(builder.call_count, 1)
            finally:
                release.set()
                worker.join(3)
            self.assertEqual(len(results), 1)

    def test_failed_report_is_not_cached_and_health_is_never_cached(self):
        provider = ObservationReadOnlyStatusProvider(repo_root=Path('.'), target=object())
        with patch.object(provider, '_status_document', side_effect=[RuntimeError('failed'),
                {'telegram_body': 'ok', 'document': {}}, {'status': 'READY'}, {'status': 'NOT_READY'}]) as build:
            with self.assertRaises(RuntimeError):
                provider.status('learning')
            provider.status('learning')
            self.assertEqual(provider.status('observation')['status'], 'READY')
            self.assertEqual(provider.status('observation')['status'], 'NOT_READY')
            self.assertEqual(build.call_count, 4)
