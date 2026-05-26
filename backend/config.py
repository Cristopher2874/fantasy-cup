import os
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - config still works without YAML support
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_yaml_config() -> dict:
    raw_path = os.getenv("FANTASY_CUP_CONFIG", "configs.yaml")
    config_path = Path(raw_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists() or not config_path.read_text(encoding="utf-8").strip():
        return {}
    if yaml is None:
        return {}
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def config_value(config: dict, *keys: str, default=None):
    value = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def configured_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


load_dotenv(PROJECT_ROOT / ".env")
CONFIG = load_yaml_config()


class Settings:
    project_root = PROJECT_ROOT
    host = os.getenv("FANTASY_CUP_HOST", config_value(CONFIG, "app", "host", default="127.0.0.1"))
    port = int(os.getenv("FANTASY_CUP_PORT", config_value(CONFIG, "app", "port", default=8000)))
    runner = os.getenv("FANTASY_CUP_RUNNER", config_value(CONFIG, "app", "runner", default="mock"))
    debug = bool_value(os.getenv("FANTASY_CUP_DEBUG", config_value(CONFIG, "app", "debug", default=True)))

    data_dir = configured_path(os.getenv("FANTASY_CUP_DATA_DIR", config_value(CONFIG, "app", "data_dir", default="data")))
    state_dir = data_dir / "state"
    source_dir = data_dir / "source"
    uploads_dir = data_dir / "uploads"
    snapshots_dir = data_dir / "snapshots"
    artifacts_dir = data_dir / "artifacts"
    runs_dir = data_dir / "runs"
    schemas_dir = project_root / "schemas"
    frontend_dir = project_root / "frontend"

    api_sports_key = os.getenv("APISPORTS_KEY")
    api_sports_league_id = os.getenv("APISPORTS_LEAGUE_ID", config_value(CONFIG, "football_api", "league_id"))
    api_sports_season = os.getenv("APISPORTS_SEASON", config_value(CONFIG, "football_api", "season"))
    api_sports_timezone = os.getenv(
        "APISPORTS_TIMEZONE",
        config_value(CONFIG, "football_api", "timezone", default="UTC"),
    )


settings = Settings()
