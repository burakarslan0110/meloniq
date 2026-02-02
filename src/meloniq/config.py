import json
import os
from pathlib import Path
from typing import Dict, Any

class Config:
    """Simple configuration manager for persisting user settings."""
    
    _instance = None
    _defaults = {
        "language": "en",  # Default to English
        "theme": "light"
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _get_config_path(self) -> Path:
        """Get path to config file in user's home directory."""
        app_dir = Path.home() / ".meloniq"
        app_dir.mkdir(exist_ok=True)
        return app_dir / "settings.json"

    def _load(self):
        """Load settings from disk."""
        self._settings = self._defaults.copy()
        path = self._get_config_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._settings.update(data)
            except Exception:
                pass  # Use defaults on error

    def save(self):
        """Save settings to disk."""
        path = self._get_config_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=4)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        self._settings[key] = value
        self.save()

    @property
    def language(self) -> str:
        return self._settings.get("language", "en")

    @language.setter
    def language(self, value: str):
        self.set("language", value)
