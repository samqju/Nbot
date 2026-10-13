"""Read-only service preflight must refuse legacy, host and branch conflicts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from nbot.v5.g1f_preflight import verify_startup, LEGACY_UNITS


class G1fPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.data=root/"data"
        self.data.mkdir()
        self.repo=root/"sandbox"
        (self.repo/"nbot/v5").mkdir(parents=True)
        (self.repo/"nbot/v5/g1f_runner.py").write_text("# test source")
        self.states={name:"inactive" for name in LEGACY_UNITS}
        self.branch="v5-clean-restart-20261013"

    def run_command(self,argv,**kwargs):
        if argv[0]=="git":
            return SimpleNamespace(returncode=0,stdout=self.branch+"\n")
        if argv[0]=="systemctl":
            return SimpleNamespace(returncode=3,stdout=self.states[argv[-1]]+"\n")
        self.fail("Unexpected subprocess "+str(argv))

    def check(self,host="base"):
        return verify_startup(
            hostname=host,runner=self.run_command,
            path=self.data,repo=self.repo,
        )

    def test_all_legacy_inactive_correct_host_and_branch_passes(self):
        self.assertEqual(self.check(),())

    def test_wrong_host_never_runs_execution_collector(self):
        self.assertIn("NOT_OBSERVATION_VPS",self.check("nbot-execution"))

    def test_any_active_legacy_unit_blocks_observation_startup(self):
        for unit in LEGACY_UNITS:
            with self.subTest(unit=unit):
                self.states[unit]="active"
                self.assertIn("LEGACY_ACTIVE_OR_UNKNOWN_"+unit,self.check())
                self.states[unit]="inactive"

    def test_wrong_branch_and_missing_runner_block(self):
        self.branch="main"
        self.assertIn("ISOLATED_V5_BRANCH_INVALID",self.check())
        self.branch="v5-clean-restart-20261013"
        (self.repo/"nbot/v5/g1f_runner.py").unlink()
        self.assertIn("ISOLATED_V5_CODE_NOT_PRESENT",self.check())

    def test_missing_or_symlinked_database_directory_blocks(self):
        self.data.rmdir()
        self.assertIn("ISOLATED_DB_DIRECTORY_INVALID",self.check())
        self.data.symlink_to(self.repo,target_is_directory=True)
        self.assertIn("ISOLATED_DB_DIRECTORY_INVALID",self.check())


if __name__=="__main__":
    unittest.main()
