import logging

from typing import Any
from pathlib import Path

from envyaml import EnvYAML
from dotenv import load_dotenv

load_dotenv()

DEFAULT_APP_CONFIG = Path(__file__).resolve().with_name("config.yaml")

class GlobalConfigProvider:

    _instance = None
    _initialized=False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalConfigProvider, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._config_path = DEFAULT_APP_CONFIG
        self._scfg = self._load_config(str(self._config_path))
        self._initialized = True

    def _load_config(self, config_path: str) -> EnvYAML | None:
        """Load configuration from a YAML file."""
        try:
            return EnvYAML(config_path)
        except FileNotFoundError:
            print(f"Error: Configuration file '{config_path}' not found.")
            return None
        
    def get_config_value(self, section: str, key: str, default: Any = None) -> Any:
        """Get value from config.yaml given section and key"""
        if not self._scfg:
            return default
        section_data = self._scfg.get(section, {})
        if not isinstance(section_data, dict):
            return default
        value = section_data.get(key, default)
        return value

    def get_str(self, section: str, key: str, default: str) -> str:
        value = self.get_config_value(section, key, default)
        return str(value)

    def get_int(self, section: str, key: str, default: int) -> int:
        value = self.get_config_value(section, key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_float(self, section: str, key: str, default: float) -> float:
        value = self.get_config_value(section, key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_bool(self, section: str, key: str, default: bool) -> bool:
        value = self.get_config_value(section, key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.casefold() in {"1", "true", "yes", "on"}
        return bool(value)
