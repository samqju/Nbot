"""Static contract for isolated G1g hourly health units."""
from pathlib import Path
import unittest


class G1gServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/"deploy/v5"
        cls.service=(base/"nbot-v5-g1g-health.service").read_text()
        cls.timer=(base/"nbot-v5-g1g-health.timer").read_text()

    def test_read_only_no_service_or_order_authority(self):
        for entry in (
            "Type=oneshot", "User=ubuntu",
            "nbot.v5.g1g_health", "Restart=no",
            "ProtectSystem=strict", "ProtectHome=read-only",
            "NoNewPrivileges=true", "RestrictAddressFamilies=AF_UNIX",
            "MemoryMax=64M", "CPUQuota=25%",
        ):
            self.assertIn(entry,self.service)
        for forbidden in ("ReadWritePaths","binance_key","nbot-execution",
                          "nbot.v5.g1f_runner --db","sudo ","Restart=always"):
            self.assertNotIn(forbidden,self.service)

    def test_timer_does_not_run_more_than_hourly(self):
        for item in ("OnUnitActiveSec=1h","OnBootSec=8min",
                     "Persistent=true","WantedBy=timers.target",
                     "nbot-v5-g1g-health.service"):
            self.assertIn(item,self.timer)
        self.assertNotIn("OnUnitActiveSec=1min",self.timer)
        self.assertNotIn("nbot-v4-",self.timer)


if __name__ == "__main__":
    unittest.main()
