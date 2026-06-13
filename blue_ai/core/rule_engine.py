"""
BLUE_AI Rule Engine — Kural tabanlı karar motoru.

TOML formatında tanımlanmış kuralları değerlendirir ve aksiyonları tetikler.
"""

import operator
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

from blue_ai.core.logger import get_logger


@dataclass
class Rule:
    """Tek bir kural tanımı."""
    name: str
    condition: str
    action: str
    priority: str = "normal"
    cooldown: float = 60.0  # saniye
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)
    _last_triggered: float = 0.0


_OPERATORS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

# Koşul ayrıştırma regex'i: "metric_name op value"
_CONDITION_PATTERN = re.compile(
    r"(\w+(?:\.\w+)*)\s*(>=|<=|==|!=|>|<)\s*([\d.]+)"
)


class RuleEngine:
    """Kural tabanlı karar motoru."""

    def __init__(self) -> None:
        self._rules: list[Rule] = []
        self._logger = get_logger()
        self._action_registry: dict[str, Any] = {}

    def load_rules_from_toml(self, path: Path) -> int:
        """TOML dosyasından kuralları yükle."""
        with open(path, "rb") as f:
            data = tomllib.load(f)

        count = 0
        for rule_data in data.get("rules", []):
            cooldown_str = rule_data.get("cooldown", "60s")
            cooldown = self._parse_duration(cooldown_str)

            rule = Rule(
                name=rule_data["name"],
                condition=rule_data["condition"],
                action=rule_data["action"],
                priority=rule_data.get("priority", "normal"),
                cooldown=cooldown,
                enabled=rule_data.get("enabled", True),
                params=rule_data.get("params", {}),
            )
            self._rules.append(rule)
            count += 1

        self._logger.info("RuleEngine", f"{count} kural yüklendi: {path.name}")
        return count

    def add_rule(self, rule: Rule) -> None:
        """Programatik olarak kural ekle."""
        self._rules.append(rule)

    def register_action(self, action_name: str, handler: Any) -> None:
        """Aksiyon handler'ı kaydet."""
        self._action_registry[action_name] = handler

    def evaluate(self, context: dict[str, float]) -> list[tuple[Rule, str]]:
        """Tüm kuralları verilen bağlamda değerlendir.

        Returns:
            Tetiklenen (kural, aksiyon) çiftlerinin listesi.
        """
        triggered: list[tuple[Rule, str]] = []
        now = time.time()

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Cooldown kontrolü
            if now - rule._last_triggered < rule.cooldown:
                continue

            if self._evaluate_condition(rule.condition, context):
                rule._last_triggered = now
                triggered.append((rule, rule.action))
                self._logger.action(
                    "RuleEngine",
                    f"Kural tetiklendi: {rule.name} → {rule.action}",
                    f"Koşul: {rule.condition}",
                )

        return triggered

    def _evaluate_condition(self, condition: str, context: dict[str, float]) -> bool:
        """Koşul ifadesini değerlendir.

        Desteklenen format:
            "metric > value"
            "metric1 > value1 AND metric2 < value2"
            "metric1 > value1 OR metric2 < value2"
        """
        # AND/OR ile bölme
        condition = condition.strip()

        if " AND " in condition:
            parts = condition.split(" AND ")
            return all(self._evaluate_single(p.strip(), context) for p in parts)
        elif " OR " in condition:
            parts = condition.split(" OR ")
            return any(self._evaluate_single(p.strip(), context) for p in parts)
        else:
            return self._evaluate_single(condition, context)

    def _evaluate_single(self, expr: str, context: dict[str, float]) -> bool:
        """Tek bir koşul ifadesini değerlendir."""
        match = _CONDITION_PATTERN.match(expr)
        if not match:
            return False

        metric_name = match.group(1)
        op_str = match.group(2)
        threshold = float(match.group(3))

        value = context.get(metric_name)
        if value is None:
            return False

        op_func = _OPERATORS.get(op_str)
        if op_func is None:
            return False

        return op_func(value, threshold)

    @staticmethod
    def _parse_duration(s: str) -> float:
        """Süre string'ini saniyeye çevir (örn: '60s', '5m', '1h')."""
        s = s.strip().lower()
        if s.endswith("s"):
            return float(s[:-1])
        elif s.endswith("m"):
            return float(s[:-1]) * 60
        elif s.endswith("h"):
            return float(s[:-1]) * 3600
        else:
            try:
                return float(s)
            except ValueError:
                return 60.0

    def get_rules(self) -> list[Rule]:
        """Tüm kuralları getir."""
        return list(self._rules)

    def enable_rule(self, name: str) -> bool:
        """Kuralı etkinleştir."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, name: str) -> bool:
        """Kuralı devre dışı bırak."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = False
                return True
        return False

    def remove_rule(self, name: str) -> bool:
        """Kuralı kaldır."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False
