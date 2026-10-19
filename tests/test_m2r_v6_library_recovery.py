"""Offline-only contract tests; must not start any systemd service or Docker."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import m2r_v6_library_failure_recovery as m

class RecoverySafety(unittest.TestCase):
    def test_exact_seven_missing_jobs_and_no_successful_reruns(self):
        self.assertEqual(len(m.JOBS),7)
        self.assertEqual({j[0] for j in m.JOBS},
                         {"hyperopt","lgbm","adaptive","rl"})
        self.assertEqual([j[0] for j in m.JOBS].count("hyperopt"),3)
        self.assertEqual([j[0] for j in m.JOBS].count("lgbm"),2)
        self.assertNotIn("native",[j[0] for j in m.JOBS])
        self.assertNotIn("trailing",[j[0] for j in m.JOBS])
        self.assertNotIn("baseline",[j[0] for j in m.JOBS])

    def test_no_consent_cannot_execute(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"CONSENT"):
                m.preflight()

    def test_unique_isolated_paths_and_pinned_source(self):
        self.assertEqual(len({m.folder_for(j) for j in m.JOBS}),7)
        self.assertNotEqual(m.OUT,m.PREV)
        self.assertIn("source",str(m.SOURCE))
        self.assertEqual(len(m.GIT_SHA),40)
        self.assertEqual(m.NEXT,"nbot-v6-profit-protection-next-20261018.service")

    def test_source_no_paper_or_live_or_overwrite(self):
        src=(ROOT/"scripts/m2r_v6_library_failure_recovery.py").read_text()
        ast.parse(src)
        self.assertIn("PARTIAL_RECOVERY_OUTPUT_REQUIRES_REVIEW",src)
        self.assertIn("OWNER_AUTHORIZED_OFFLINE",src)
        self.assertNotIn("create_order(",src)
        self.assertNotIn("systemctl\",\"stop",src)

    def test_all_service_units_are_persistent_and_nonrecurring(self):
        for name in ("nbot-v6-profit-protection-next-20261018",
                     "nbot-v6-library-recovery-20261018"):
            content=(ROOT/"deploy"/(name+".service")).read_text()
            self.assertIn("Restart=no",content)
            self.assertIn("[Install]",content)
            self.assertIn("WantedBy=multi-user.target",content)
            self.assertNotIn("Freqtrade dry-run",content)

if __name__=="__main__":unittest.main()
