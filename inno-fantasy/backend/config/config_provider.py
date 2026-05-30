import logging

from typing import Any
from envyaml import EnvYAML
from dotenv import load_dotenv
load_dotenv()

DEFAULT_APP_CONFIG="./backend/config/config.yaml"

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
        self._scfg = self._load_config(self._config_path)       
        self._initialized = True

    def _load_config(self, config_path: str) -> EnvYAML | None:
        """Load configuration from a YAML file."""
        try:
            return EnvYAML(config_path)
        except FileNotFoundError:
            print(f"Error: Configuration file '{config_path}' not found.")
            return None
        
    def get_config_value(self, section: str, key: str, default: str | None = None) -> str | None:
        """Get value from config.yaml given section and key"""
        if not self._scfg:
            return default
        section_data = self._scfg.get(section, {})
        if not isinstance(section_data, dict):
            return default
        value = section_data.get(key, default)
        return value
