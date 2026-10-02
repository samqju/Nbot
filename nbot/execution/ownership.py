"""Cross-profile runtime ownership and safe switching, independent of networking."""
from contextlib import contextmanager
from pathlib import Path
from nbot.config.profiles import PROFILES
from nbot.exchange.binance_testnet import _InstanceLock
from nbot.execution.state import ExecutionStatePaths, ExecutionStateStore
from nbot.execution.outcomes import PendingOutcomeOutbox


def require_profile_flat(root, name):
    profile = PROFILES[name]
    paths = ExecutionStatePaths.for_profile(Path(root), name)
    if PendingOutcomeOutbox(paths.pending_outcomes_dir).pending_count():
        raise ValueError("MODE_SWITCH_PENDING_OUTCOME:" + name)
    if not paths.state_file.exists():
        return
    store = ExecutionStateStore(paths.state_file, profile=name, market_environment=profile.market_environment)
    snap = store.snapshot
    if snap.open_position or snap.entry_inflight or snap.recovery.critical or snap.entries_enabled:
        raise ValueError("MODE_SWITCH_PROFILE_NOT_SAFELY_STOPPED:" + name)


@contextmanager
def execution_ownership(root, profile_name, *, arming=False):
    root = Path(root)
    global_lock = _InstanceLock(root/"runtime/execution/active-profile.lock")
    global_lock.acquire()
    legacy_locks = []
    try:
        for name, profile in PROFILES.items():
            if name != profile_name or arming:
                # Detect older workers that do not yet use the shared lock.
                lock = _InstanceLock(root/"runtime/execution"/profile.execution_state_dir.name/"execution.lock")
                lock.acquire()
                legacy_locks.append(lock)
                require_profile_flat(root, name)
        yield
    finally:
        for lock in reversed(legacy_locks):
            lock.release()
        global_lock.release()
