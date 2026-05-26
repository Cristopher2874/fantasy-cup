from pathlib import Path

from backend.runners.base import AgentRunner


class HostedContainerRunner(AgentRunner):
    def run(self, team: dict, snapshot: dict, matchday: dict, artifact_path: str, run_dir: Path) -> dict:
        raise NotImplementedError(
            "Hosted container execution is planned after the local mock loop is stable."
        )
