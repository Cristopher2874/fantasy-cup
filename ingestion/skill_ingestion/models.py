from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationReport:
    source_path: Path
    skill_name: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def health_label(self) -> str:
        return "healthy" if self.is_valid else "invalid"


@dataclass
class IngestionResult:
    zip_path: Path
    status: str
    message: str
    report: ValidationReport | None = None
    stored_path: Path | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "stored"
