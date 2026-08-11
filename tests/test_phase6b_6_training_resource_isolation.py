import unittest
from pathlib import Path


class Phase6B6TrainingResourceIsolationTests(unittest.TestCase):
    def test_auto_training_service_has_hard_realtime_protection(self):
        service = Path(
            "deploy/observation/nbot-auto-training.service.in"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "scripts.learning.auto_train --watch",
            service,
        )
        self.assertIn("Nice=10", service)
        self.assertIn("IOSchedulingClass=idle", service)
        self.assertIn("CPUWeight=10", service)
        self.assertIn("IOWeight=10", service)
        self.assertIn("CPUQuota=75%", service)

        for variable in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            self.assertIn(
                f"Environment={variable}=1",
                service,
            )

        # Resource isolation must remain on the learning service only.
        observation = Path(
            "deploy/observation/nbot-observation.service.in"
        ).read_text(encoding="utf-8")
        self.assertNotIn("CPUQuota=", observation)


if __name__ == "__main__":
    unittest.main()
