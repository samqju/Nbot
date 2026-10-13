"""Static safety gate for the future isolated V5 systemd observer."""
from pathlib import Path
import unittest


class G1fServiceSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=(
            Path(__file__).resolve().parents[1]/
            "deploy/v5/nbot-v5-observation-only.service"
        ).read_text()

    def test_service_not_a_trading_executor(self):
        self.assertIn("User=ubuntu",self.text)
        self.assertIn("nbot.v5.g1f_runner",self.text)
        self.assertIn("Environment=PYTHONDONTWRITEBYTECODE=1",self.text)
        self.assertNotIn("binance_api_key",self.text.lower())
        self.assertNotIn("api-secret",self.text.lower())
        self.assertNotIn("nbot-execution",self.text.lower())

    def test_limits_and_no_self_restart(self):
        for required in (
            "Restart=no","MemoryMax=200M","CPUQuota=75%",
            "ExecCondition=/home/ubuntu/nbot_v5_venv/bin/python -m nbot.v5.g1f_preflight",
            "NoNewPrivileges=true","ProtectSystem=strict",
            "ReadWritePaths=/home/ubuntu/nbot_v5_data",
            "PrivateTmp=true","UMask=0077",
            "--max-seconds 0","--top 50",
        ):
            self.assertIn(required,self.text)

    def test_legacy_directory_is_never_writable(self):
        self.assertNotIn("ReadWritePaths=/home/ubuntu/Nbot",self.text)
        self.assertNotIn("ExecStart=/home/ubuntu/Nbot/",self.text)
        self.assertNotIn("Restart=always",self.text)


if __name__=="__main__":
    unittest.main()
