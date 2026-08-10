import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase53CSingleEntrypointTests(unittest.TestCase):
    def test_only_split_role_entrypoints_remain(self):
        self.assertTrue((ROOT / "run_execution.py").is_file())
        self.assertTrue((ROOT / "run_observation.py").is_file())
        self.assertFalse((ROOT / "run.py").exists())
        self.assertFalse((ROOT / "runtime_runner.py").exists())
        self.assertFalse((ROOT / "run_live.py").exists())
        self.assertFalse((ROOT / "run_testnet.py").exists())

    def test_learning_scripts_are_importable_as_modules(self):
        modules = [
            "scripts.learning.build_dataset",
            "scripts.learning.time_split",
            "scripts.learning.train_baseline",
            "scripts.learning.evaluate_model",
            "scripts.learning.ensemble_experiment",
            "scripts.learning.evaluate_shadow_promotion",
            "scripts.safety.live_readonly_check",
        ]

        for module in modules:
            with self.subTest(module=module):
                imported = importlib.import_module(module)
                self.assertTrue(callable(getattr(imported, "main", None)))

    def test_old_root_utility_names_are_removed(self):
        old_names = [
            "run_dataset_build.py",
            "run_time_split.py",
            "run_baseline_train.py",
            "run_model_evaluation.py",
            "run_ensemble_experiment.py",
            "run_shadow_promotion.py",
            "run_live_readonly_check.py",
        ]

        for name in old_names:
            with self.subTest(name=name):
                self.assertFalse((ROOT / name).exists())


if __name__ == "__main__":
    unittest.main()
