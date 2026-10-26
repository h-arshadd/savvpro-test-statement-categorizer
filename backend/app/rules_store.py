import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()


class RulesStore:
    """Saved 'this merchant is always this category' rules, kept in a small JSON file."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def all(self) -> dict[str, str]:
        with _LOCK:
            return self._read()

    def set(self, merchant: str, category: str) -> None:
        with _LOCK:
            rules = self._read()
            rules[merchant] = category
            self._write(rules)

    def delete(self, merchant: str) -> bool:
        """Remove a saved rule. Returns False if there was no rule for that merchant."""
        with _LOCK:
            rules = self._read()
            if merchant not in rules:
                return False
            del rules[merchant]
            self._write(rules)
            return True

    def _read(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def _write(self, rules: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(rules, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic: never leaves a half-written file