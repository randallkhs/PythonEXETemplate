"""Persistent local config for ACS-AI-Image-Reproducer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_DIR = Path.home() / ".acs-ai-image-reproducer"
CONFIG_PATH = APP_DIR / "config.json"


@dataclass
class RuntimeStats:
    openai_avg_seconds: float = 30.0
    gemini_avg_seconds: float = 25.0


class AppConfig:
    """Simple JSON-backed configuration store."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "stats": {
                    "openai_avg_seconds": 30.0,
                    "gemini_avg_seconds": 25.0,
                },
                "last_output_dir": str(Path.home()),
            }

        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return {}
            return loaded
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get_last_output_dir(self) -> Path:
        raw = self._data.get("last_output_dir")
        if isinstance(raw, str) and raw.strip():
            return Path(raw).expanduser()
        return Path.home()

    def set_last_output_dir(self, output_dir: Path) -> None:
        self._data["last_output_dir"] = str(output_dir.expanduser().resolve())
        self.save()

    def get_provider_avg_seconds(self, provider: str) -> float:
        stats = self._data.get("stats", {})
        if not isinstance(stats, dict):
            return 30.0
        key = f"{provider}_avg_seconds"
        value = stats.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        return 30.0

    def update_provider_avg_seconds(self, provider: str, elapsed_seconds: float) -> None:
        if elapsed_seconds <= 0:
            return
        stats = self._data.setdefault("stats", {})
        if not isinstance(stats, dict):
            stats = {}
            self._data["stats"] = stats
        key = f"{provider}_avg_seconds"
        previous = stats.get(key)
        if isinstance(previous, (int, float)) and previous > 0:
            stats[key] = round((float(previous) * 0.7) + (elapsed_seconds * 0.3), 3)
        else:
            stats[key] = round(elapsed_seconds, 3)
        self.save()
