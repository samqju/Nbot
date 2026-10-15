"""CS-00 read-only host telemetry. Explicitly NOT a service watchdog.

No network, subprocess execution, environment/secret values or disk writes.
Samples resource availability once and returns an unsigned PRESTART HOLD.
"""
from __future__ import annotations
import os
import re
from pathlib import Path

from .cs00_commissioning import CommissioningHold, CommissioningPolicy

SCHEMA="NBOT_V5_1_CS00_READ_ONLY_HOST_PROBE_V1"
_MIB=1024*1024


def _available_memory_bytes(path: Path = Path("/proc/meminfo")) -> int:
    # Linux-only. No process environment, files in the user's home or
    # secrets are accessed.
    raw=path.read_text(encoding="ascii")
    match=re.search(r"^MemAvailable:\s+(\d+) kB$",raw,re.MULTILINE)
    if match is None:
        raise CommissioningHold("CS00_MEM_AVAILABLE_NOT_KNOWN")
    return int(match.group(1))*1024


def inspect_offline_host(*, disk_mount:Path=Path("/tmp"),
                         meminfo:Path=Path("/proc/meminfo")) ->dict:
    policy=CommissioningPolicy().validate()
    if (not isinstance(disk_mount,Path) or not disk_mount.is_absolute()
        or disk_mount.is_symlink() or not disk_mount.is_dir()
        or not isinstance(meminfo,Path) or not meminfo.is_absolute()
        or meminfo.is_symlink()):
        raise CommissioningHold("CS00_HOST_PROBE_UNSAFE_PATH")
    disk=os.statvfs(disk_mount)
    free=disk.f_bavail*disk.f_frsize
    available=_available_memory_bytes(meminfo)
    cpus=os.cpu_count()
    load=os.getloadavg()[0]
    if (type(cpus) is not int or cpus<1 or
        available<0 or free<0):
        raise CommissioningHold("CS00_HOST_TELEMETRY_UNKNOWN")
    warnings=[]
    if free<policy.minimum_free_disk_bytes:
        warnings.append("FREE_DISK_RESERVE_HOLD")
    if available < 128*_MIB:
        warnings.append("AVAILABLE_RAM_LOW_HOLD")
    if load>cpus*1.5:
        warnings.append("HIGH_SYSTEM_LOAD_REVIEW")
    return {"schema":SCHEMA,"kind":"READ_ONLY_ONE_TIME_SAMPLE",
            "cpu_logical":cpus,
            "load_1minute":round(load,4),
            "mem_available_kib":available//1024,
            "disk_available_mib":free//_MIB,
            "monitored_disk_mount":str(disk_mount),
            "alerts":warnings,
            "source_collector_started_by_probe":False,
            "nbot_services_modified_by_probe":False,
            "actual_archive_provider_contacted":False,
            "actual_live_source_qualified":False,
            "trading_authority":"NONE",
            "commissioning_go":"HOLD_PENDING_CS00_C_E_AND_OWNER_PERMISSION"}
