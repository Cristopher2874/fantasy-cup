from pathlib import Path

from backend.runners.base import AgentRunner


class CodexCliRunner(AgentRunner):
    def run(self, team: dict, snapshot: dict, matchday: dict, artifact_path: str, run_dir: Path) -> dict:
        raise NotImplementedError(
            "Codex CLI runner is optional and not enabled in the phase 1 local POC."
        )
