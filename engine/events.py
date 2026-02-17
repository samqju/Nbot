from dataclasses import dataclass

@dataclass
class EngineEvent:
    severity: str
    category: str
    money_at_risk: bool
    requires_flatten: bool
    requires_disable: bool
    retryable: bool
    reason: str
