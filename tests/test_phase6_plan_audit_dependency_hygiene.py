from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "requirements.lock.txt"
DEV = ROOT / "requirements-dev.lock.txt"


class Phase6PlanAuditDependencyHygieneTests(unittest.TestCase):
    def test_runtime_lock_excludes_development_only_lint_packages(self):
        runtime = RUNTIME.read_text(encoding="utf-8").lower()
        for package in ("flake8", "mccabe", "pycodestyle", "pyflakes"):
            self.assertNotIn(f"{package}==", runtime)

    def test_development_lock_layers_on_runtime_and_pins_lint_packages(self):
        dev = DEV.read_text(encoding="utf-8").lower()
        self.assertIn("-r requirements.lock.txt", dev)
        for package in ("flake8", "mccabe", "pycodestyle", "pyflakes"):
            self.assertRegex(dev, rf"(?m)^{package}==[^\s]+$")

    def test_production_deployment_installs_runtime_lock_only(self):
        for relative in ("deploy/FRESH_INSTALL.md", "deploy/README.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("requirements.lock.txt", text)
            self.assertIn("requirements-dev.lock.txt", text)
            self.assertNotIn(
                'pip install -r "$NBOT_REPO/requirements-dev.lock.txt"',
                text,
            )

    def test_runtime_source_does_not_import_lint_tooling(self):
        forbidden = ("flake8", "mccabe", "pycodestyle", "pyflakes")
        for path in ROOT.rglob("*.py"):
            if ".git" in path.parts or "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for package in forbidden:
                self.assertNotIn(f"import {package}", text)
                self.assertNotIn(f"from {package}", text)


if __name__ == "__main__":
    unittest.main()
