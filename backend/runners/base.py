from abc import ABC, abstractmethod
from pathlib import Path


class AgentRunner(ABC):
    @abstractmethod
    def run(self, team: dict, snapshot: dict, matchday: dict, artifact_path: str, run_dir: Path) -> dict:
        raise NotImplementedError
