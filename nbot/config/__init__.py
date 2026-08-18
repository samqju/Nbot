"""V3 named profile and machine-role configuration."""

from .profiles import PROFILES, Profile, get_profile
from .validation import MachineRole, detect_role

__all__ = ["PROFILES", "Profile", "get_profile", "MachineRole", "detect_role"]
