from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    name: str
    market_environment: str
    execution_mode: str
    capital_kind: str
    execution_state_dir: Path
    observation_db: Path
    evidence_lineage: str
    binance_order_writes: bool
    real_capital: bool
    requires_arm_gate: bool

    def validate(self) -> None:
        if self.name not in {"testnet-trade", "live-paper", "live-trade"}:
            raise ValueError("NBOT_PROFILE_NAME_INVALID")
        if self.market_environment not in {"TESTNET", "LIVE"}:
            raise ValueError("NBOT_MARKET_ENVIRONMENT_INVALID")
        if self.execution_mode not in {"TRADE", "PAPER"}:
            raise ValueError("NBOT_EXECUTION_MODE_INVALID")
        if self.real_capital and not self.binance_order_writes:
            raise ValueError("NBOT_REAL_CAPITAL_WITHOUT_ORDER_WRITES")
        if self.name == "live-paper" and self.binance_order_writes:
            raise ValueError("NBOT_LIVE_PAPER_ORDER_WRITES_FORBIDDEN")
        if self.name == "live-trade" and not self.requires_arm_gate:
            raise ValueError("NBOT_LIVE_TRADE_ARM_GATE_REQUIRED")
        if self.name == "testnet-trade" and self.market_environment != "TESTNET":
            raise ValueError("NBOT_TESTNET_PROFILE_ENVIRONMENT_MISMATCH")
        if self.name.startswith("live-") and self.market_environment != "LIVE":
            raise ValueError("NBOT_LIVE_PROFILE_ENVIRONMENT_MISMATCH")


PROFILES: dict[str, Profile] = {
    "testnet-trade": Profile(
        name="testnet-trade",
        market_environment="TESTNET",
        execution_mode="TRADE",
        capital_kind="TESTNET_FAKE",
        execution_state_dir=Path("data/execution/testnet"),
        observation_db=Path("data/observation/testnet/observer.db"),
        evidence_lineage="TESTNET_OPERATIONAL_ONLY",
        binance_order_writes=True,
        real_capital=False,
        requires_arm_gate=True,
    ),
    "live-paper": Profile(
        name="live-paper",
        market_environment="LIVE",
        execution_mode="PAPER",
        capital_kind="LOCAL_PAPER",
        execution_state_dir=Path("data/execution/paper"),
        observation_db=Path("data/observation/live/observer.db"),
        evidence_lineage="LIVE_PAPER_OPERATIONAL",
        binance_order_writes=False,
        real_capital=False,
        requires_arm_gate=False,
    ),
    "live-trade": Profile(
        name="live-trade",
        market_environment="LIVE",
        execution_mode="TRADE",
        capital_kind="REAL",
        execution_state_dir=Path("data/execution/real"),
        observation_db=Path("data/observation/live/observer.db"),
        evidence_lineage="LIVE_REAL_CAPITAL",
        binance_order_writes=True,
        real_capital=True,
        requires_arm_gate=True,
    ),
}

for _profile in PROFILES.values():
    _profile.validate()


def get_profile(name: str) -> Profile:
    try:
        return PROFILES[str(name).strip().lower()]
    except KeyError as exc:
        raise ValueError("NBOT_PROFILE_UNKNOWN") from exc
