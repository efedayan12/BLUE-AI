"""
BLUE_AI Rules Models — Kural veri modelleri.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleCondition:
    """Kural koşulu."""
    metric: str
    operator: str  # >, <, >=, <=, ==, !=
    value: float


@dataclass
class RuleAction:
    """Kural aksiyonu."""
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleDefinition:
    """Kural tanımı — seri hale getirme / TOML export için."""
    name: str
    conditions: list[RuleCondition]
    action: RuleAction
    priority: str = "normal"
    cooldown: float = 60.0
    enabled: bool = True
    logic: str = "AND"  # AND / OR

    def to_toml_dict(self) -> dict[str, Any]:
        """TOML formatına çevir."""
        cond_parts = []
        for c in self.conditions:
            cond_parts.append(f"{c.metric} {c.operator} {c.value}")
        condition_str = f" {self.logic} ".join(cond_parts)

        return {
            "name": self.name,
            "condition": condition_str,
            "action": self.action.action_type,
            "priority": self.priority,
            "cooldown": f"{self.cooldown}s",
            "enabled": self.enabled,
            "params": self.action.params,
        }
