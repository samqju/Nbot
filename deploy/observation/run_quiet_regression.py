"""Run full unittest suite with clean dot progress, without hiding failures.

All test stdout/stderr (including OS-fd writes and child processes) are captured
to an ephemeral file. unittest's own progress and summary use a duplicate of
the original console FD and remain visible. On failure the captured diagnostic
stream is printed after unittest's traceback. This wrapper alters no tests.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest


def run_quiet(*, start_directory: str = "tests", pattern: str = "test_*.py") -> int:
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    sys.stdout.flush()
    sys.stderr.flush()
    saved_stdout_fd = os.dup(1)
    saved_stderr_fd = os.dup(2)
    console = os.fdopen(os.dup(saved_stdout_fd), "w", buffering=1, encoding="utf-8")
    result = None
    captured_text = ""
    try:
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as capture:
            try:
                os.dup2(capture.fileno(), 1)
                os.dup2(capture.fileno(), 2)
                suite = unittest.defaultTestLoader.discover(start_directory, pattern=pattern)
                runner = unittest.TextTestRunner(stream=console, verbosity=1)
                result = runner.run(suite)
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                os.dup2(saved_stdout_fd, 1)
                os.dup2(saved_stderr_fd, 2)
            if result is not None and not result.wasSuccessful():
                capture.seek(0)
                captured_text = capture.read()
    finally:
        console.close()
        os.close(saved_stdout_fd)
        os.close(saved_stderr_fd)

    if result is None:
        return 2
    if not result.wasSuccessful():
        if captured_text:
            print("\n=== Captured output from unsuccessful test run ===", file=sys.stderr)
            print(captured_text, file=sys.stderr, end="" if captured_text.endswith("\n") else "\n")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-directory", default="tests")
    parser.add_argument("--pattern", default="test_*.py")
    arguments = parser.parse_args()
    return run_quiet(start_directory=arguments.start_directory, pattern=arguments.pattern)


if __name__ == "__main__":
    raise SystemExit(main())
