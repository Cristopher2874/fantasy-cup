from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGESTION_ROOT = PROJECT_ROOT / "ingestion"

# Drop uploaded skill zip files here, then run:
# uv run python -m ingestion.skill_ingestion
ZIP_UPLOAD_DIR = INGESTION_ROOT / "data" / "skill_zips"
VALID_SKILLS_DIR = INGESTION_ROOT / "skills"
STAGING_ROOT = INGESTION_ROOT / "data" / "skill_ingestion_staging"

# Demo safety limits. These keep accidental huge uploads from being expanded.
MAX_ZIP_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
MAX_FILE_COUNT = 100
MAX_SKILL_MD_BYTES = 250_000
MAX_SKILL_BODY_LINES = 500

# Keep this false for demos so a repeat upload cannot silently replace a skill.
REPLACE_EXISTING_SKILLS = False

SKILL_NAME_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
REQUIRED_FRONTMATTER_KEYS = frozenset({"name", "description"})
STRICT_FRONTMATTER_KEYS = True

ALLOWED_TOP_LEVEL_NAMES = frozenset(
    {
        "SKILL.md",
        "agents",
        "scripts",
        "references",
        "assets",
    }
)
OPTIONAL_RESOURCE_DIRS = frozenset({"agents", "scripts", "references", "assets"})
IGNORED_ZIP_PARTS = frozenset({"__MACOSX", ".DS_Store"})
