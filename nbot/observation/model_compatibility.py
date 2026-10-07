"""Compatibility of persisted training artifacts across operational releases.

Compare training/feature dependencies, not the whole deployment revision.
Inference still validates every artifact version, digest, cutoff and rejection.
"""
from pathlib import Path
import re
import subprocess

def compatible_training_release(repo_root: Path, trained_sha: str, running_sha: str) -> bool:
    if not all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{40}", x)
               for x in (trained_sha, running_sha)):
        return False
    if trained_sha == running_sha:
        return True
    # Training, feature definitions, data contracts, shared utilities and the
    # base runtime dependency manifests must be identical. Admin orchestration
    # and downstream inference consumers do not define persisted Ridge
    # coefficients/features, so adding Selective ML must not strand an already
    # valid frozen Ridge challenger.
    paths = ["nbot/observation", "nbot/common", "nbot/config",
             "requirements*", "pyproject.toml", "poetry.lock", "uv.lock",
             "setup.py", "setup.cfg", "Pipfile", "Pipfile.lock",
             ":(exclude)nbot/observation/learned_recommendation.py",
             ":(exclude)nbot/observation/recommendation.py",
             ":(exclude)nbot/observation/model_compatibility.py",
             ":(exclude)nbot/observation/paper_feedback.py",
             ":(exclude)nbot/observation/feedback_evidence.py",
             ":(exclude)nbot/observation/paper_learning_report.py",
             ":(exclude)nbot/observation/shadow.py",
             ":(exclude)nbot/observation/selective_ml.py",
             ":(exclude)requirements-ml.txt"]
    try:
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", trained_sha, running_sha],
            cwd=repo_root, capture_output=True, timeout=3)
        if ancestor.returncode != 0:
            return False
        diff = subprocess.run(["git", "diff", "--no-ext-diff", "--name-only",
                               trained_sha, running_sha, "--", *paths],
                              cwd=repo_root, capture_output=True, timeout=3)
        return diff.returncode == 0 and not diff.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False
