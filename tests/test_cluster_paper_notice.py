import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

loader=importlib.machinery.SourceFileLoader("cluster_paper_notice_ctl",str(Path(__file__).parents[1]/"nbotctl"))
spec=importlib.util.spec_from_loader(loader.name,loader)
ctl=importlib.util.module_from_spec(spec)
loader.exec_module(ctl)
NOTICE="LIVE_PAPER_OPERATIONAL_CANARY_HAS_NO_ECONOMIC_AUTHORITY"

class PaperNoticeTests(unittest.TestCase):
    def test_paper_disclaimer_does_not_block_start(self):
        self.assertEqual(ctl._cluster_local_warnings("live-paper",{"warnings":[NOTICE]}),[])

    def test_real_safety_errors_still_block(self):
        self.assertEqual(ctl._cluster_local_warnings("live-paper",
            {"warnings":[NOTICE,"GIT_WORKTREE_DIRTY","EXECUTION_SINGLE_INSTANCE_LOCK_HELD"]}),
            ["GIT_WORKTREE_DIRTY","EXECUTION_SINGLE_INSTANCE_LOCK_HELD"])

    def test_other_modes_do_not_ignore_warnings(self):
        for profile in ("live-trade","testnet-trade"):
            self.assertEqual(ctl._cluster_local_warnings(profile,{"warnings":[NOTICE,"PROFILE_DISARMED"]}),
                             [NOTICE,"PROFILE_DISARMED"])
