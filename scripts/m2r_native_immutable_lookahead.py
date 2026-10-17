"""Research-only Freqtrade 2026.9 lookahead diagnosis with immutable saved models.

This is NOT a replacement for stock official lookahead-analysis. Freqtrade's
native FreqAI lookahead implementation deletes its identifier model folder
before every shortened replay, so native comparisons can refit *different*
models. In this explicit V6 offline diagnostic, suppress only that deletion
of an isolated copied identifier; no calls to native model training are
permitted. Do NOT put this in a production entrypoint.

Run in network-disabled one-shot Docker with a scratch copy of already saved
25 model bundles. Never mount the source model directory here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-userdir", required=True, type=Path)
    parser.add_argument("--expected-identifier", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--expected-models", default=25, type=int)
    parser.add_argument("freqtrade_args", nargs=argparse.REMAINDER)
    a = parser.parse_args()
    if not a.expected_identifier.startswith("nbot-v6-m2r-native-purged-models-frozen-"):
        raise RuntimeError("V6_RESEARCH_ONLY_MODEL_IDENTIFIER_REQUIRED")
    scratch = a.scratch_userdir.resolve()
    model_root = (scratch / "models" / a.expected_identifier).resolve()
    if scratch not in model_root.parents or not model_root.is_dir():
        raise RuntimeError("ISOLATED_MODEL_COPY_REQUIRED")
    if model_root.is_symlink():
        raise RuntimeError("ISOLATED_MODEL_COPY_CANNOT_BE_SYMLINK")
    binary_paths = sorted(model_root.glob("sub-train-*/*_model.joblib"))
    if len(binary_paths) != a.expected_models:
        raise RuntimeError(f"REQUIRE_ALL_SAVED_MODELS found={len(binary_paths)}")
    before = {str(p.relative_to(model_root)): sha256(p) for p in binary_paths}

    if not a.freqtrade_args or a.freqtrade_args[0] != "--":
        raise RuntimeError("ONLY_EXPLICIT_OFFLINE_FREQTRADE_LOOKAHEAD_ALLOWED")
    ftargs = a.freqtrade_args[1:]
    if not ftargs or ftargs[0] != "lookahead-analysis":
        raise RuntimeError("ONLY_STOCK_LOOKAHEAD_ANALYSIS_COMMAND_ALLOWED")
    # Forbid interacting with exchange. Runtime config also has empty keys and
    # tested Docker must have --network none.
    if "--userdir" not in ftargs or Path(
        ftargs[ftargs.index("--userdir") + 1]
    ).resolve() != scratch:
        raise RuntimeError("REQUIRE_SCRATCH_USERDIR")

    from freqtrade.optimize.analysis import lookahead as native_lookahead
    from freqtrade.freqai.prediction_models.LightGBMRegressor import LightGBMRegressor

    deleted = []
    training = []
    native_shutil = native_lookahead.shutil

    class ProtectedShutil:
        @staticmethod
        def rmtree(target, *args, **kwargs):
            target_path = Path(target).resolve()
            if target_path != model_root:
                raise RuntimeError(f"UNEXPECTED_MODEL_DELETE_BLOCKED {target_path}")
            deleted.append(str(target_path))
            print(f"FROZEN_REPLAY_PREVENTED_MODEL_FOLDER_DELETION #{len(deleted)}", flush=True)

        def __getattr__(self, name):
            return getattr(native_shutil, name)

    native_lookahead.shutil = ProtectedShutil()

    def forbid_retrain(self, *args, **kwargs):
        training.append(str(args[1] if len(args)>1 else "unknown"))
        raise RuntimeError("FROZEN_REPLAY_TRAINING_FORBIDDEN")

    LightGBMRegressor.train = forbid_retrain
    try:
        from freqtrade.main import main as freqtrade_main
        # Preserve the upstream diagnostic's command sentinel for the existing
        # NbotV6M2Audit safety guard. Without this, its lookahead-only startup
        # intentionally refuses Freqtrade's unlimited simulated slots.
        sys.argv = ["freqtrade", *ftargs]
        try:
            freqtrade_main(ftargs)
            cli_exit = 0
        except SystemExit as exc:
            cli_exit = int(exc.code or 0) if isinstance(exc.code, int) or not exc.code else 1
    finally:
        native_lookahead.shutil = native_shutil

    after_files = sorted(model_root.glob("sub-train-*/*_model.joblib"))
    after = {str(p.relative_to(model_root)): sha256(p) for p in after_files}
    report = {
        "experiment": "Stock Freqtrade 2026.9 lookahead-analysis with ONLY deletion suppressed in isolated saved-model copy; native LightGBM model training forbidden",
        "model_identifier": a.expected_identifier,
        "model_file_count_before": len(before),
        "model_file_count_after": len(after),
        "model_hash_differences": [k for k in before if after.get(k) != before[k]],
        "model_delete_attempts_prevented": len(deleted),
        "retraining_attempts": training,
        "native_cli_exit_code": cli_exit,
        "strict_fixed_model_integrity_pass": cli_exit == 0 and not training and before == after and len(deleted)>0,
        "caveat": "Any has_bias=Yes recorded in the native official table must still be examined by column and signal; suppressing FreqAI folder cleanup does not guarantee a no-bias verdict or correct strategy."
    }
    a.report.write_text(json.dumps(report, indent=2) + "\n")
    print("FROZEN_LOOKAHEAD_GUARDED_DIAGNOSTIC", json.dumps(report), flush=True)
    return 0 if report["strict_fixed_model_integrity_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
