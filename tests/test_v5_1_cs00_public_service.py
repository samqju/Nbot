"""CS-00 public Observation future foreground service activation remains locked."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from nbot_v5_1.cs00_public_service import (
    FutureCs01Permit,FuturePublicObservationService,PublicServiceHold)

SHA="a"*40

def approval(**kwargs):
    d=dict(project="NBOT_V5.1",branch="nbot-v5.1",
           exact_commit_sha=SHA,release_action_id="CS01-OWNER-APPROVAL-EXAMPLE",
           approved_mode="PUBLIC_OBSERVATION_ONLY",expires_at_ms=200000)
    d.update(kwargs)
    return FutureCs01Permit(**d)

class CS00FuturePublicServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="cs00-future-service-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.app=FuturePublicObservationService(source_root=self.root,code_sha=SHA)

    def test_CSSVC01_constructor_does_not_start_anything(self):
        self.assertFalse(self.app.status()["source_process_started"])
        self.assertFalse(self.app.status()["exchange_order_capability"])
        self.assertFalse(self.app.status()["paper_enabled"])
        self.assertEqual(self.app.status()["financial_authority"],"NONE")

    def test_CSSVC02_missing_owner_permit_fails_before_network(self):
        with patch("scripts.g2_readonly_probe.probe",side_effect=AssertionError("NET")):
            with self.assertRaises(PublicServiceHold):
                self.app.run_foreground(permit=None,expected_exact_sha=SHA)
        self.assertFalse(self.app.started)

    def test_CSSVC03_wrong_revision_denied_before_network(self):
        with self.assertRaises(PublicServiceHold):
            self.app.run_foreground(permit=approval(exact_commit_sha="b"*40),
                                    expected_exact_sha=SHA)
        self.assertFalse(self.app.started)

    def test_CSSVC04_nonpublic_mode_denied(self):
        with self.assertRaises(PublicServiceHold):
            approval(approved_mode="PAPER").validate(expected_sha=SHA,now_ms=1000)

    def test_CSSVC05_expired_approval_denied(self):
        with self.assertRaises(PublicServiceHold):
            approval(expires_at_ms=1000).validate(expected_sha=SHA,now_ms=1000)

    def test_CSSVC06_approval_not_considered_source_authentication(self):
        p=approval()
        p.validate(expected_sha=SHA,now_ms=1000)
        self.assertEqual(self.app.status()["mode"],"STOPPED_CS00")

    def test_CSSVC07_manual_stop_is_locked_state_not_order_client(self):
        self.app.request_stop("OWNER_PREFERENCE")
        self.assertFalse(self.app.started)
        self.assertEqual(self.app.status()["stop_reason"],"OWNER_PREFERENCE")
        self.assertEqual(self.app.status()["financial_authority"],"NONE")

if __name__=="__main__":unittest.main()
