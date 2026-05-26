from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
import hashlib
import json
import secrets

from backend.config import settings


STATE_DEFAULTS = {
    "teams": [],
    "submissions": [],
    "snapshots": [],
    "matchdays": [],
    "runs": [],
    "leaderboard": [],
}


class StateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.ensure()

    def ensure(self) -> None:
        for directory in [
            settings.state_dir,
            settings.source_dir,
            settings.uploads_dir,
            settings.snapshots_dir,
            settings.artifacts_dir,
            settings.runs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        for name, default in STATE_DEFAULTS.items():
            path = self._state_path(name)
            if not path.exists():
                self.write_json(path, default)

    def read(self, name: str) -> list[dict]:
        with self._lock:
            path = self._state_path(name)
            if not path.exists():
                return []
            return json.loads(path.read_text(encoding="utf-8"))

    def write(self, name: str, records: list[dict]) -> None:
        with self._lock:
            self.write_json(self._state_path(name), records)

    def append(self, name: str, record: dict) -> dict:
        with self._lock:
            records = self.read(name)
            records.append(record)
            self.write(name, records)
            return record

    def update(self, name: str, record_id: str, replacement: dict) -> dict:
        with self._lock:
            records = self.read(name)
            for index, record in enumerate(records):
                if record.get("id") == record_id:
                    records[index] = replacement
                    self.write(name, records)
                    return replacement
        raise KeyError(f"{name} record not found: {record_id}")

    def find_by_id(self, name: str, record_id: str) -> dict | None:
        for record in self.read(name):
            if record.get("id") == record_id:
                return record
        return None

    def next_id(self, prefix: str, name: str) -> str:
        records = self.read(name)
        highest = 0
        for record in records:
            record_id = str(record.get("id", ""))
            if record_id.startswith(f"{prefix}-"):
                try:
                    highest = max(highest, int(record_id.split("-")[-1]))
                except ValueError:
                    continue
        return f"{prefix}-{highest + 1:03d}"

    def write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)

    def _state_path(self, name: str) -> Path:
        if name not in STATE_DEFAULTS:
            raise KeyError(f"Unknown state file: {name}")
        return settings.state_dir / f"{name}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_token() -> str:
    return secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


store = StateStore()
