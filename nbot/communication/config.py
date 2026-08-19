"""Profile-scoped V3 control-link runtime configuration.

The control link carries only bounded Observation/Execution protocol messages.
It never carries Binance private credentials or market-data streams.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from nbot.config.loader import merged_environment
from nbot.config.profiles import Profile

from .auth import validate_control_token


CONTROL_LINK_SECRET_FILE = Path("config/secrets/control-link.env")

_PROFILE_URL_KEYS = {
    "testnet-trade": "NBOT_OBSERVATION_TESTNET_URL",
    "live-paper": "NBOT_OBSERVATION_LIVE_PAPER_URL",
}


@dataclass(frozen=True)
class ControlLinkConfig:
    base_url: str
    auth_token: str
    timeout_seconds: float = 2.0
    ca_file: Path | None = None

    def validate(self) -> None:
        if not self.base_url or self.base_url != self.base_url.strip():
            raise ValueError("NBOT_OBSERVATION_URL_REQUIRED")
        validate_control_token(self.auth_token)
        timeout = float(self.timeout_seconds)
        if not (0.1 <= timeout <= 30.0):
            raise ValueError("NBOT_OBSERVATION_TIMEOUT_INVALID")
        if self.ca_file is not None and not Path(self.ca_file).is_file():
            raise ValueError("NBOT_OBSERVATION_CA_FILE_MISSING")


def control_link_secret_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / CONTROL_LINK_SECRET_FILE


def control_link_environment(
    repo_root: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load ignored control-link config, then allow exported values to override it."""

    path = control_link_secret_path(repo_root)
    if not path.is_file():
        raise ValueError("NBOT_CONTROL_LINK_SECRET_FILE_MISSING")
    mode = path.stat().st_mode & 0o777
    if mode != 0o600:
        raise ValueError("NBOT_CONTROL_LINK_SECRET_FILE_MODE_INVALID")
    return merged_environment(path, environ=environ)


def control_link_config_for_profile(
    repo_root: str | Path,
    profile: Profile,
    *,
    environ: Mapping[str, str] | None = None,
) -> ControlLinkConfig:
    """Return the fail-closed remote Observation endpoint for one profile.

    V3.6 enables only the TESTNET dry integration target.  LIVE/PAPER uses the
    same protocol but its integrated runtime remains a later roadmap phase.
    """

    if profile.name == "live-trade":
        raise ValueError("NBOT_OBSERVATION_LIVE_TRADE_FORBIDDEN_BEFORE_V3_10")
    try:
        url_key = _PROFILE_URL_KEYS[profile.name]
    except KeyError as exc:
        raise ValueError("NBOT_CONTROL_LINK_PROFILE_UNSUPPORTED") from exc

    env = control_link_environment(repo_root, environ=environ)
    base_url = str(env.get(url_key) or env.get("NBOT_OBSERVATION_URL") or "").strip()
    auth_token = str(env.get("NBOT_CONTROL_AUTH_TOKEN", "")).strip()
    timeout_raw = str(env.get("NBOT_OBSERVATION_TIMEOUT_SECONDS", "2.0")).strip()
    ca_raw = str(env.get("NBOT_OBSERVATION_CA_FILE", "")).strip()

    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("NBOT_OBSERVATION_TIMEOUT_INVALID") from exc

    ca_file = None if not ca_raw else Path(ca_raw)
    if ca_file is not None and not ca_file.is_absolute():
        ca_file = Path(repo_root) / ca_file

    config = ControlLinkConfig(
        base_url=base_url,
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
        ca_file=ca_file,
    )
    config.validate()
    return config
