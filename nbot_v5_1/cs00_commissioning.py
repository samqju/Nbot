"""CS-00 nontrading Observation commissioning foundation (OFFLINE ONLY).

No socket, HTTP, Binance identity, account/order API, model inference,
autostart, service supervisor, persistent deployment or credential handling.
All inputs are injected by offline tests; genuine source acquisition is a
SEPARATELY APPROVED CS-01 adapter that does not exist in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import time

from .core import FiveMinuteEvent, INTERVAL_MS
from .observation import ObservationBook, ClosedBar
from .exploration import explore_event
from .deep_selection import choose_deep
from .deep_segments import DeepSegmentRecorder, DeepSegmentHold
from .archive_custody import seal_archive, verify_archive

SCHEMA = "NBOT_V5_1_CS00_OFFLINE_ONLY_V1"
_GRADE = "SYNTHETIC_OFFLINE_TEST_ONLY"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}\Z")
_VALID_STATUS = ("PASS_OFFLINE", "HOLD", "FAIL")
MAX_REPORT_BYTES = 65536


class CommissioningHold(ValueError):
    pass


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      allow_nan=False, separators=(",", ":")).encode("ascii")


def _sha(obj):
    return sha256(_canon(obj)).hexdigest()


def _private_directory(path: Path):
    if (not isinstance(path, Path) or not path.is_absolute() or
            path.is_symlink() or not path.is_dir()):
        raise CommissioningHold("CS00_PRIVATE_DIRECTORY_REQUIRED")
    s = path.stat()
    if s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise CommissioningHold("CS00_DIRECTORY_OWNER_PERMISSIONS")


def _read_safe(path: Path, max_bytes: int) -> bytes:
    if not isinstance(path, Path) or path.is_symlink():
        raise CommissioningHold("CS00_FILE_SYMLINK")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid()
                or s.st_nlink != 1 or s.st_mode & 0o077
                or s.st_size > max_bytes):
            raise CommissioningHold("CS00_REPORT_UNSAFE")
        body = os.read(fd, max_bytes + 1)
        if len(body) != s.st_size:
            raise CommissioningHold("CS00_REPORT_INCOMPLETE")
        return body
    finally:
        os.close(fd)


@dataclass(frozen=True)
class CommissioningPolicy:
    source_mode: str = "OFFLINE_SYNTHETIC_FIXTURE_ONLY"
    financial_authority: str = "NONE"
    public_network_enabled: bool = False
    production_service_enabled: bool = False
    autostart_enabled: bool = False
    virtual_research_enabled: bool = False
    paper_enabled: bool = False
    testnet_enabled: bool = False
    real_trading_enabled: bool = False
    model_promotion_enabled: bool = False
    archive_deletion_enabled: bool = False
    external_alerts_enabled: bool = False
    retention_planning_days: int = 30
    broad_count: int = 100
    deep_count: int = 20
    virtual_slot_ceiling: int = 40
    maximum_rss_kib: int = 256000
    maximum_boundary_ms: int = 1500
    maximum_frame_queue: int = 5000
    minimum_free_disk_bytes: int = 512 * 1024 * 1024

    def validate(self):
        safe_bool = (self.public_network_enabled,
                     self.production_service_enabled, self.autostart_enabled,
                     self.virtual_research_enabled, self.paper_enabled,
                     self.testnet_enabled, self.real_trading_enabled,
                     self.model_promotion_enabled, self.archive_deletion_enabled,
                     self.external_alerts_enabled)
        ints = (self.retention_planning_days, self.broad_count,
                self.deep_count, self.virtual_slot_ceiling,
                self.maximum_rss_kib, self.maximum_boundary_ms,
                self.maximum_frame_queue, self.minimum_free_disk_bytes)
        if (self.source_mode != "OFFLINE_SYNTHETIC_FIXTURE_ONLY" or
            self.financial_authority != "NONE" or
            any(type(x) is not bool or x for x in safe_bool) or
            any(type(x) is not int for x in ints) or
            self.retention_planning_days != 30 or self.broad_count != 100 or
            self.deep_count != 20 or self.virtual_slot_ceiling != 40 or
            not 100000 <= self.maximum_rss_kib <= 400000 or
            not 100 <= self.maximum_boundary_ms <= 10000 or
            not 100 <= self.maximum_frame_queue <= 5000 or
            self.minimum_free_disk_bytes < 128*1024*1024):
            raise CommissioningHold("CS00_POLICY_NEVER_PERMIT_NETWORK_ORDER_OR_DELETION")
        return self

    def digest(self) -> str:
        self.validate()
        return _sha(self.__dict__)


@dataclass(frozen=True)
class ArchivePlan:
    """Nonsecret profile only. No provider connection or deleted data."""
    provider_label: str = "OWNER_EXISTING_PROVIDER_UNSPECIFIED"
    destination_type: str = "UNSELECTED"
    retention_days_target: int = 30
    deletion_permission: bool = False
    credential_attached: bool = False
    destination_verified: bool = False
    bytes_per_day_observed: int | None = None
    budget_bytes: int | None = None

    def validate(self):
        if (type(self.provider_label) is not str or
                _LABEL.fullmatch(self.provider_label) is None or
                self.destination_type not in (
                    "UNSELECTED", "S3_COMPATIBLE", "SFTP",
                    "CLOUD_OBJECT_STORAGE", "OTHER") or
                type(self.retention_days_target) is not int or
                self.retention_days_target != 30 or
                type(self.deletion_permission) is not bool or self.deletion_permission or
                type(self.credential_attached) is not bool or self.credential_attached or
                type(self.destination_verified) is not bool or self.destination_verified or
                self.bytes_per_day_observed is not None and (
                    type(self.bytes_per_day_observed) is not int or
                    self.bytes_per_day_observed < 0) or
                self.budget_bytes is not None and (
                    type(self.budget_bytes) is not int or
                    self.budget_bytes < 1024*1024)):
            raise CommissioningHold("CS00_ARCHIVE_PROFILE_NO_KEYS_OR_RELEASE")
        return self

    def planning_status(self):
        self.validate()
        return {
            "provider": self.provider_label,
            "destination_type": self.destination_type,
            "retention_target_days": 30,
            "no_automatic_deletion": True,
            "actual_provider_contacted": False,
            "actual_offhost_archival_verified": False,
            "budget_capacity_confirmed": False if self.budget_bytes is None else
                                         self.bytes_per_day_observed is not None,
            "illustrative_30day_bytes": (
                self.bytes_per_day_observed * 30
                if self.bytes_per_day_observed is not None else None),
            "state": "CS00_PROVIDER_CONFIGURATION_AND_LIVE_CAPACITY_HOLD",
        }


@dataclass(frozen=True)
class ObservationOfflineProof:
    event_open_ms: int
    universe_sha: str
    snapshot_sha: str
    exploration_sha: str
    deep_manifest_sha: str
    broad: int
    directions: int
    deep: int
    metadata_ready: int
    source_held: int
    synthetic_source_frames: int
    action: str = "NO_TRADE"
    financial_authority: str = "NONE"
    original_grade_witnessed: bool = False


class OfflineObservationRunner:
    """Deterministic 5m coordinator over existing G2/G3/G4 code.

    No lifecycle start method, threads, socket acquisition, timer or trading.
    Caller supplies already closed candles with explicit receipt clocks.
    The raw-frame custody seam ONLY accepts synthetic fixtures; a genuine
    source adapter needs a separate review, signed CS-01 and new release.
    """

    def __init__(self, observation: ObservationBook,
                 policy: CommissioningPolicy = CommissioningPolicy()):
        if type(observation) is not ObservationBook or type(policy) is not CommissioningPolicy:
            raise CommissioningHold("CS00_OBSERVATION_CONFIG")
        policy.validate()
        if len(observation.manifest.symbols) != 100:
            raise CommissioningHold("CS00_BROAD_COHORT_MUST_BE_100")
        self.book = observation
        self.policy = policy
        self.last_event_ms: int | None = None
        self.deep = None
        self.proofs: list[ObservationOfflineProof] = []
        self.recorder: DeepSegmentRecorder | None = None
        self.frames = 0
        self.alarms: list[str] = []
        self.pending_frame_count = 0

    def on_closed_bar(self, bar: ClosedBar, *, decision_at_ms: int):
        if type(bar) is not ClosedBar or type(decision_at_ms) is not int:
            raise CommissioningHold("CS00_INVALID_FINALIZED_BAR")
        if self.last_event_ms is not None and bar.open_ms <= self.last_event_ms:
            self.alarms.append("STALE_CANDLE_AFTER_BOUNDARY")
            raise CommissioningHold("CS00_CANNOT_RETROFIT_OLD_CANDLE")
        valid = self.book.ingest(bar, decision_at_ms=decision_at_ms)
        if not valid:
            self.alarms.append("BAR_GAP_OR_UNQUALIFIED")
        return valid

    def on_five_minute(self, event: FiveMinuteEvent) -> ObservationOfflineProof:
        if type(event) is not FiveMinuteEvent or (
                self.last_event_ms is not None and
                event.event_open_ms <= self.last_event_ms):
            raise CommissioningHold("CS00_BOUNDARY_REPLAY_OR_WRONG_CLOCK")
        start = time.perf_counter()
        snapshot = self.book.snapshot(event)
        # Deliberately ZERO Research slots: no virtual admission and no
        # detector-heavy research evaluation before a separate CS-03 release.
        batch = explore_event(self.book, event, capacity_slots=0)
        deep = choose_deep(self.book.manifest, batch, count=20)
        if (len(snapshot.rows) != 100 or len(batch.rows) != 200 or
                len(deep.symbols) != 20 or "BTCUSDT" not in deep.symbols or
                not deep.no_trade or batch.evaluated_pairs != 0 or
                batch.capacity_skipped_pairs + batch.source_skipped_pairs != 200 or
                any(x.source_grade != "WARMUP_HOLD_NOT_ORIGINAL_VERIFIED"
                    for x in deep.entries)):
            raise CommissioningHold("CS00_100_200_20_OR_SOURCE_CONTRACT_BREACH")
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= self.policy.maximum_boundary_ms:
            self.alarms.append("FIVE_MINUTE_BUDGET_EXCEEDED")
        self.deep = deep
        self.last_event_ms = event.event_open_ms
        record = ObservationOfflineProof(
            event.event_open_ms, snapshot.universe_sha, snapshot.snapshot_id,
            batch.batch_id, deep.manifest_sha,
            len(snapshot.rows), len(batch.rows), len(deep.symbols),
            snapshot.healthy_count, snapshot.hold_count, self.frames)
        self.proofs.append(record)
        if snapshot.hold_count:
            self.alarms.append("PUBLIC_CANDLE_METADATA_SOURCE_HOLD")
        return record

    def bind_synthetic_raw_recorder(self, root: Path, *,
                                    quota_bytes: int = 64*1024*1024):
        if self.deep is None or self.recorder is not None:
            raise CommissioningHold("CS00_DEEP_COHORT_NOT_FROZEN_OR_REBIND")
        _private_directory(root)
        self.recorder = DeepSegmentRecorder(
            root, symbols=self.deep.symbols, quota_bytes=quota_bytes)

    def accept_synthetic_raw(self, *, kind: str, raw: bytes,
                             received_at_ms: int, epoch: int):
        if self.recorder is None or type(raw) is not bytes:
            raise CommissioningHold("CS00_RAW_SOURCE_NOT_BOUND")
        if (type(received_at_ms) is not int or received_at_ms <= 0 or
                type(epoch) is not int or epoch < 1):
            raise CommissioningHold("CS00_SOURCE_EPOCH_OR_CLOCK")
        if self.pending_frame_count >= self.policy.maximum_frame_queue:
            self.alarms.append("SOURCE_BACKPRESSURE_HOLD")
            raise CommissioningHold("CS00_BOUNDED_FRAME_QUEUE_FULL")
        self.pending_frame_count += 1
        try:
            result = self.recorder.append(
                kind=kind, raw=raw,
                received_at_ms=received_at_ms, epoch=epoch)
        except DeepSegmentHold:
            self.alarms.append("ORIGINAL_SHAPED_SYNTHETIC_SOURCE_GAP")
            return False
        finally:
            self.pending_frame_count -= 1
        if result.state == "HOLD":
            self.alarms.append("ORIGINAL_SHAPED_SYNTHETIC_SOURCE_GAP")
            return False
        self.frames += 1
        return True

    def flush_synthetic(self):
        if self.recorder is None:
            raise CommissioningHold("CS00_NO_RECORDER")
        return self.recorder.flush()

    def archive_locally_for_offline_test(self, destination: Path):
        if self.recorder is None or self.deep is None:
            raise CommissioningHold("CS00_NO_TEST_SOURCE")
        _private_directory(destination)
        self.flush_synthetic()
        sealed = seal_archive(
            source=self.recorder.root, destination=destination,
            symbols=self.deep.symbols)
        checked = verify_archive(root=destination,symbols=self.deep.symbols)
        if checked["frames"] != self.frames:
            raise CommissioningHold("CS00_SYNTHETIC_REPLAY_FRAME_MISMATCH")
        return checked

    def status(self, *, rss_kib: int | None = None,
               free_disk_bytes: int | None = None,
               source_queue_depth: int = 0) -> dict:
        self.policy.validate()
        for name,val in (("rss_kib",rss_kib),
                         ("free_disk_bytes",free_disk_bytes)):
            if val is not None and (type(val) is not int or val<0):
                raise CommissioningHold("CS00_MONITOR_INVALID")
        if type(source_queue_depth) is not int or source_queue_depth < 0:
            raise CommissioningHold("CS00_QUEUE_INVALID")
        alerts=set(self.alarms)
        if rss_kib is not None and rss_kib >= self.policy.maximum_rss_kib:
            alerts.add("RAM_HIGH_HOLD")
        if (free_disk_bytes is not None and
                free_disk_bytes < self.policy.minimum_free_disk_bytes):
            alerts.add("FREE_DISK_RESERVE_HOLD")
        if source_queue_depth >= self.policy.maximum_frame_queue:
            alerts.add("SOURCE_BACKPRESSURE_HOLD")
        # Never infer source qualification from a flat health dashboard.
        return {"schema":SCHEMA, "mode":self.policy.source_mode,
                "running":False, "public_network":False,
                "actual_exchange_orders":0,"virtual_positions":0,
                "paper_positions":0,"real_positions":0,
                "model_authority":"NONE","original_source_verified":False,
                "archive_offhost_verified":False,
                "financial_authority":"NONE","event_count":len(self.proofs),
                "synthetic_frames":self.frames,
                "retention_days_target":30,"deletion_allowed":False,
                "alerts":sorted(alerts),
                "decision":"HOLD" if alerts else "NO_TRADE"}


def write_immutable_offline_report(directory: Path, name: str, payload: dict):
    """Private O_EXCL+fsync report, no overwrite/rotation/HTTP or auto-delete."""
    _private_directory(directory)
    if (type(name) is not str or
            not re.fullmatch(r"[a-z][a-z0-9_-]{1,50}\.json",name) or
            type(payload) is not dict or
            payload.get("financial_authority") != "NONE" or
            payload.get("original_source_verified") is not False):
        raise CommissioningHold("CS00_REPORT_MODE_OR_NAME")
    content={"schema":SCHEMA, "payload":payload,"payload_sha256":_sha(payload)}
    raw=_canon(content)+b"\n"
    if len(raw)>MAX_REPORT_BYTES:
        raise CommissioningHold("CS00_REPORT_SIZE")
    path=directory/name
    if path.is_symlink() or path.exists():
        raise CommissioningHold("CS00_IMMUTABLE_REPORT_ALREADY_EXISTS")
    fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        remainder=memoryview(raw)
        while remainder:
            written=os.write(fd,remainder)
            if written<=0:
                raise CommissioningHold("CS00_REPORT_SHORT_WRITE")
            remainder=remainder[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return verify_immutable_offline_report(path)


def verify_immutable_offline_report(path: Path):
    _private_directory(path.parent)
    raw=_read_safe(path,MAX_REPORT_BYTES)
    try:
        d=json.loads(raw,object_pairs_hook=_no_duplicates)
    except (ValueError,TypeError,UnicodeError) as e:
        raise CommissioningHold("CS00_REPORT_BAD_JSON") from e
    if (type(d) is not dict or set(d)!={"schema","payload","payload_sha256"}
            or d["schema"]!=SCHEMA or
            type(d["payload"]) is not dict or
            d["payload"].get("financial_authority")!="NONE" or
            d["payload"].get("original_source_verified") is not False or
            _sha(d["payload"])!=d["payload_sha256"] or
            _canon(d)+b"\n"!=raw):
        raise CommissioningHold("CS00_REPORT_TAMPER_OR_UNAUTHORIZED")
    return d


def _no_duplicates(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise CommissioningHold("CS00_DUPLICATE_JSON_KEY")
        out[k]=v
    return out
