import asyncio
import unittest
from nbot.v5.g4_forward_capture_runner import run_bounded,G4CollectorHold


class SustainedCaptureTests(unittest.TestCase):
    def test_extended_budget_requires_explicit_opt_in(self):
        with self.assertRaises(G4CollectorHold):
            asyncio.run(run_bounded(vault=None,endpoints={},connector=None,
                                    duration_s=14401,max_frames=1000000,max_db_mib=1000))

    def test_sustained_budget_still_capped(self):
        with self.assertRaises(G4CollectorHold):
            asyncio.run(run_bounded(vault=None,endpoints={},connector=None,
                                    duration_s=21601,max_frames=1000000,max_db_mib=1000,sustained=True))
