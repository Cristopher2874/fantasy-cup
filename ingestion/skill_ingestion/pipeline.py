from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .config import (
    IGNORED_ZIP_PARTS,
    MAX_FILE_COUNT,
    MAX_UNCOMPRESSED_BYTES,
    MAX_ZIP_BYTES,
    REPLACE_EXISTING_SKILLS,
    STAGING_ROOT,
    VALID_SKILLS_DIR,
    ZIP_UPLOAD_DIR,
)
from .models import IngestionResult, ValidationReport
from .validator import validate_skill_folder


def ingest_all_skill_zips(
    upload_dir: Path = ZIP_UPLOAD_DIR,
    destination_dir: Path = VALID_SKILLS_DIR,
) -> list[IngestionResult]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination_dir.mkdir(parents=True, exist_ok=True)

    return [ingest_skill_zip(zip_path, destination_dir) for zip_path in sorted(upload_dir.glob("*.zip"))]


def ingest_skill_zip(zip_path: Path, destination_dir: Path = VALID_SKILLS_DIR) -> IngestionResult:
    zip_path = zip_path.resolve()
    destination_dir = destination_dir.resolve()

    zip_errors = _validate_zip_container(zip_path)
    if zip_errors:
        report = ValidationReport(source_path=zip_path, errors=zip_errors)
        return IngestionResult(zip_path=zip_path, status="invalid", message="Zip file failed validation.", report=report)

    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    destination_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="skill-", dir=STAGING_ROOT) as staging_name:
        staging_dir = Path(staging_name).resolve()
        extract_errors = _extract_zip_safely(zip_path, staging_dir)
        if extract_errors:
            report = ValidationReport(source_path=zip_path, errors=extract_errors)
            return IngestionResult(
                zip_path=zip_path,
                status="invalid",
                message="Zip file could not be extracted safely.",
                report=report,
            )

        skill_root, root_errors, root_warnings, require_folder_name = _find_skill_root(staging_dir)
        if root_errors or skill_root is None:
            report = ValidationReport(source_path=zip_path, errors=root_errors, warnings=root_warnings)
            return IngestionResult(zip_path=zip_path, status="invalid", message="No valid skill root was found.", report=report)

        report = validate_skill_folder(skill_root, require_folder_name=require_folder_name)
        report.source_path = zip_path
        report.warnings.extend(root_warnings)
        if not report.is_valid:
            return IngestionResult(zip_path=zip_path, status="invalid", message="Skill is not healthy.", report=report)

        assert report.skill_name is not None
        stored_path = destination_dir / report.skill_name
        if stored_path.exists() and not REPLACE_EXISTING_SKILLS:
            report.errors.append(f"Destination skill already exists: {stored_path}")
            return IngestionResult(
                zip_path=zip_path,
                status="conflict",
                message="Skill is healthy, but it was not stored because the destination exists.",
                report=report,
                stored_path=stored_path,
            )

        if stored_path.exists():
            _remove_existing_skill(stored_path, destination_dir)

        shutil.copytree(
            skill_root,
            stored_path,
            ignore=shutil.ignore_patterns("__MACOSX", ".DS_Store", "__pycache__"),
        )
        final_report = validate_skill_folder(stored_path, require_folder_name=True)
        final_report.source_path = zip_path
        final_report.warnings = _dedupe([*report.warnings, *final_report.warnings])
        if not final_report.is_valid:
            return IngestionResult(
                zip_path=zip_path,
                status="invalid",
                message="Skill copied, but the stored copy failed validation.",
                report=final_report,
                stored_path=stored_path,
            )

        return IngestionResult(
            zip_path=zip_path,
            status="stored",
            message="Skill is healthy and was stored.",
            report=final_report,
            stored_path=stored_path,
        )


def format_result(result: IngestionResult) -> str:
    skill_name = result.report.skill_name if result.report else None
    title = f"{result.status.upper()}: {result.zip_path.name}"
    if skill_name:
        title += f" -> {skill_name}"

    lines = [title, result.message]
    if result.stored_path:
        lines.append(f"Stored path: {result.stored_path}")

    if result.report:
        for error in result.report.errors:
            lines.append(f"ERROR: {error}")
        for warning in result.report.warnings:
            lines.append(f"WARNING: {warning}")

    return "\n".join(lines)


def main() -> int:
    results = ingest_all_skill_zips()
    if not results:
        print(f"No skill zip files found in {ZIP_UPLOAD_DIR}")
        return 0

    for index, result in enumerate(results):
        if index:
            print()
        print(format_result(result))

    return 0 if all(result.is_success for result in results) else 1


def _validate_zip_container(zip_path: Path) -> list[str]:
    errors: list[str] = []
    if not zip_path.exists():
        return [f"Missing zip file: {zip_path}"]
    if not zip_path.is_file():
        return [f"Expected a zip file, got a directory or special path: {zip_path}"]
    if zip_path.suffix.lower() != ".zip":
        errors.append("Uploaded file must have a .zip extension.")
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        errors.append(f"Zip file is larger than {MAX_ZIP_BYTES} bytes.")

    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [member for member in archive.infolist() if not _is_ignored_member(member.filename)]
    except zipfile.BadZipFile:
        return ["File is not a readable zip archive."]

    file_members = [member for member in members if not member.is_dir()]
    if not file_members:
        errors.append("Zip archive does not contain any skill files.")
    if len(file_members) > MAX_FILE_COUNT:
        errors.append(f"Zip archive has too many files; max is {MAX_FILE_COUNT}.")

    total_size = sum(member.file_size for member in file_members)
    if total_size > MAX_UNCOMPRESSED_BYTES:
        errors.append(f"Zip archive expands to more than {MAX_UNCOMPRESSED_BYTES} bytes.")

    for member in members:
        errors.extend(_validate_member_path(member.filename))

    return errors


def _extract_zip_safely(zip_path: Path, staging_dir: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if _is_ignored_member(member.filename):
                continue

            member_errors = _validate_member_path(member.filename)
            if member_errors:
                errors.extend(member_errors)
                continue

            relative_path = _member_relative_path(member.filename)
            target_path = (staging_dir / relative_path).resolve()
            if not _is_relative_to(target_path, staging_dir):
                errors.append(f"Unsafe zip member path: {member.filename}")
                continue

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)

    return errors


def _find_skill_root(staging_dir: Path) -> tuple[Path | None, list[str], list[str], bool]:
    errors: list[str] = []
    warnings: list[str] = []
    entries = [path for path in staging_dir.iterdir() if path.name not in IGNORED_ZIP_PARTS]

    if (staging_dir / "SKILL.md").is_file():
        warnings.append("Zip stores SKILL.md at the root; storing it as a canonical skill folder.")
        return staging_dir, errors, warnings, False

    if len(entries) == 1 and entries[0].is_dir():
        return entries[0], errors, warnings, True

    skill_files = [path for path in staging_dir.rglob("SKILL.md") if not _has_ignored_part(path)]
    if len(skill_files) == 1:
        errors.append("Zip must contain either SKILL.md at the root or one top-level skill folder.")
        errors.append(f"Found nested SKILL.md at: {skill_files[0].relative_to(staging_dir)}")
    elif len(skill_files) > 1:
        errors.append("Zip contains multiple SKILL.md files; upload exactly one skill at a time.")
    else:
        errors.append("Zip does not contain a required SKILL.md file.")

    return None, errors, warnings, False


def _remove_existing_skill(stored_path: Path, destination_dir: Path) -> None:
    resolved_stored_path = stored_path.resolve()
    resolved_destination_dir = destination_dir.resolve()
    if not _is_relative_to(resolved_stored_path, resolved_destination_dir):
        raise ValueError(f"Refusing to remove path outside destination: {resolved_stored_path}")
    if resolved_stored_path == resolved_destination_dir:
        raise ValueError(f"Refusing to remove destination directory itself: {resolved_stored_path}")
    if stored_path.is_dir():
        shutil.rmtree(stored_path)
    else:
        stored_path.unlink()


def _validate_member_path(member_name: str) -> list[str]:
    errors: list[str] = []
    normalized = member_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    parts = path.parts

    if not normalized or normalized.startswith("/"):
        errors.append(f"Unsafe zip member path: {member_name}")
    if parts and ":" in parts[0]:
        errors.append(f"Zip member must not contain a drive prefix: {member_name}")
    if any(part == ".." for part in parts):
        errors.append(f"Zip member must not traverse directories: {member_name}")
    if "\x00" in member_name:
        errors.append("Zip member path contains a null byte.")

    return errors


def _member_relative_path(member_name: str) -> Path:
    return Path(*PurePosixPath(member_name.replace("\\", "/")).parts)


def _is_ignored_member(member_name: str) -> bool:
    return any(part in IGNORED_ZIP_PARTS for part in PurePosixPath(member_name.replace("\\", "/")).parts)


def _has_ignored_part(path: Path) -> bool:
    return any(part in IGNORED_ZIP_PARTS for part in path.parts)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
