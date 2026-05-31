"""ZIP upload staging and safe extraction for skill validation."""
from __future__ import annotations

import inspect
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


MAX_UPLOADS = 5
MAX_ZIP_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
MAX_FILE_COUNT = 100
IGNORED_ZIP_PARTS = frozenset({"__MACOSX", ".DS_Store"})
UPLOAD_CHUNK_BYTES = 1024 * 1024


@dataclass
class ExtractedSkill:
    job_id: str
    original_filename: str
    work_dir: Path
    zip_path: Path
    extract_dir: Path
    skill_root: Path | None = None
    require_folder_name: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)


class ZipHandler:
    """Persist an uploaded zip to temp storage and extract it safely."""

    async def handle_uploaded_zip(self, upload_file: Any, job_id: str) -> ExtractedSkill:
        filename = _safe_upload_name(getattr(upload_file, "filename", None), job_id)
        work_dir = Path(tempfile.mkdtemp(prefix=f"skill-validator-{job_id}-")).resolve()
        zip_path = work_dir / filename
        extract_dir = work_dir / "extracted"
        result = ExtractedSkill(
            job_id=job_id,
            original_filename=filename,
            work_dir=work_dir,
            zip_path=zip_path,
            extract_dir=extract_dir,
        )

        save_errors = await self._save_upload(upload_file, zip_path)
        result.errors.extend(save_errors)
        if result.errors:
            return result

        result.errors.extend(_validate_zip_container(zip_path))
        if result.errors:
            return result

        extract_dir.mkdir(parents=True, exist_ok=True)
        result.errors.extend(_extract_zip_safely(zip_path, extract_dir))
        if result.errors:
            return result

        skill_root, root_errors, root_warnings, require_folder_name = _find_skill_root(extract_dir)
        result.errors.extend(root_errors)
        result.warnings.extend(root_warnings)
        result.skill_root = skill_root
        result.require_folder_name = require_folder_name
        return result

    async def _save_upload(self, upload_file: Any, target_path: Path) -> list[str]:
        errors: list[str] = []
        total_bytes = 0

        if target_path.suffix.lower() != ".zip":
            errors.append("Uploaded file must have a .zip extension.")

        try:
            with target_path.open("wb") as target:
                while True:
                    chunk = await _read_upload_chunk(upload_file, UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_ZIP_BYTES:
                        errors.append(f"Zip file is larger than {MAX_ZIP_BYTES} bytes.")
                        break
                    target.write(chunk)
        except Exception as exc:  # pragma: no cover - defensive around framework file objects
            return [f"Could not read uploaded file: {exc}"]
        finally:
            await _seek_upload_start(upload_file)

        if total_bytes == 0:
            errors.append("Uploaded zip is empty.")
        return errors


def _validate_zip_container(zip_path: Path) -> list[str]:
    errors: list[str] = []
    if not zip_path.exists():
        return [f"Missing uploaded zip file: {zip_path.name}"]
    if not zip_path.is_file():
        return [f"Expected a zip file, got a non-file path: {zip_path.name}"]
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        errors.append(f"Zip file is larger than {MAX_ZIP_BYTES} bytes.")

    try:
        with zipfile.ZipFile(zip_path) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member:
                errors.append(f"Zip archive contains a corrupt file: {corrupt_member}")

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
        if not member.is_dir() and _member_is_marked_executable(member):
            errors.append(f"Zip member is marked executable: {_normalize_member_name(member.filename)}")

    return errors


def _extract_zip_safely(zip_path: Path, destination_dir: Path) -> list[str]:
    errors: list[str] = []
    destination_root = destination_dir.resolve()

    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if _is_ignored_member(member.filename):
                continue

            member_errors = _validate_member_path(member.filename)
            if member_errors:
                errors.extend(member_errors)
                continue

            relative_path = _member_relative_path(member.filename)
            target_path = (destination_dir / relative_path).resolve()
            if not _is_relative_to(target_path, destination_root):
                errors.append(f"Unsafe zip member path: {_normalize_member_name(member.filename)}")
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

    if _has_exact_child(staging_dir, "SKILL.md"):
        warnings.append("Zip stores SKILL.md at the root; using the zip root as the skill folder.")
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


async def _read_upload_chunk(upload_file: Any, size: int) -> bytes:
    chunk = upload_file.read(size)
    if inspect.isawaitable(chunk):
        chunk = await chunk
    return chunk


async def _seek_upload_start(upload_file: Any) -> None:
    seek = getattr(upload_file, "seek", None)
    if not seek:
        return
    result = seek(0)
    if inspect.isawaitable(result):
        await result


def _safe_upload_name(filename: str | None, job_id: str) -> str:
    if not filename:
        return f"{job_id}.zip"
    normalized = filename.replace("\\", "/").strip()
    name = PurePosixPath(normalized).name
    return name or f"{job_id}.zip"


def _validate_member_path(member_name: str) -> list[str]:
    errors: list[str] = []
    normalized = _normalize_member_name(member_name)
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
    cleaned_name = _normalize_member_name(member_name).strip("/")
    return Path(*PurePosixPath(cleaned_name).parts)


def _normalize_member_name(member_name: str) -> str:
    return member_name.replace("\\", "/")


def _is_ignored_member(member_name: str) -> bool:
    cleaned_name = _normalize_member_name(member_name).strip("/")
    return any(part in IGNORED_ZIP_PARTS for part in PurePosixPath(cleaned_name).parts)


def _has_ignored_part(path: Path) -> bool:
    return any(part in IGNORED_ZIP_PARTS for part in path.parts)


def _has_exact_child(parent: Path, child_name: str) -> bool:
    return any(child.name == child_name for child in parent.iterdir())


def _member_is_marked_executable(member: zipfile.ZipInfo) -> bool:
    unix_mode = member.external_attr >> 16
    return bool(unix_mode & 0o111)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
