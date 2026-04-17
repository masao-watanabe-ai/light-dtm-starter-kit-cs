import yaml
from pathlib import Path


class RuleLoader:
    """Loads decision rules from a YAML file."""

    def load(self, path: str = "app/rules/decision_rules.yaml") -> dict:
        rule_path = Path(path)
        if not rule_path.exists():
            return {}
        with open(rule_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
