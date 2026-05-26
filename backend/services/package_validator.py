from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


SECRET_NAME_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.)", re.IGNORECASE),
    re.compile(r"(^|/).*private.*key.*", re.IGNORECASE),
    re.compile(r"(^|/).*secret.*", re.IGNORECASE),
]


def validate_zip_package(zip_path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    package_root = ""
    skill_names: list[str] = []

    if zip_path.stat().st_size > 10 * 1024 * 1024:
        errors.append("ZIP package is larger than the 10 MB local POC limit")

    try:
        with zipfile.ZipFile(zip_path) as archive:
            bad_file = archive.testzip()
            if bad_file:
                errors.append(f"ZIP package contains a corrupt file: {bad_file}")

            filenames = [normalize_zip_name(info.filename) for info in archive.infolist()]
            file_names = [name for name in filenames if name and not name.endswith("/")]

            for name in file_names:
                if is_unsafe_zip_name(name):
                    errors.append(f"Unsafe ZIP path: {name}")
                if any(pattern.search(name) for pattern in SECRET_NAME_PATTERNS):
                    warnings.append(f"Potential secret-like file included: {name}")

            package_root = detect_package_root(file_names)
            if package_root is None:
                errors.append("Package must contain a top-level skills/ folder")
                package_root = ""
            else:
                skill_names = detect_skill_names(file_names, package_root)
                if not skill_names:
                    errors.append("Package skills/ folder must contain at least one skill with SKILL.md")
    except zipfile.BadZipFile:
        errors.append("Uploaded file is not a readable ZIP package")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "package_root": package_root,
        "skills": skill_names,
    }


def validate_repo_url(repo_url: str) -> dict:
    errors: list[str] = []
    warnings = ["Local POC records the repo URL but does not clone it yet"]
    if not re.match(r"^https://(www\.)?github\.com/[^/\s]+/[^/\s]+/?$", repo_url.strip()):
        errors.append("Repo URL must be an HTTPS GitHub repository URL")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "package_root": "", "skills": []}


def extract_zip_snapshot(zip_path: Path, destination: Path, package_root: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root_prefix = f"{package_root}/" if package_root else ""
    destination_root = destination.resolve()

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            name = normalize_zip_name(info.filename)
            if not name or name.endswith("/"):
                continue
            if root_prefix and not name.startswith(root_prefix):
                continue
            relative_name = name[len(root_prefix) :] if root_prefix else name
            if is_unsafe_zip_name(relative_name):
                continue
            target_path = destination / relative_name
            if not target_path.resolve().is_relative_to(destination_root):
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def create_repo_snapshot(destination: Path, repo_url: str) -> None:
    skill_dir = destination / "skills" / "repo-placeholder"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (destination / "README.md").write_text(
        f"# Repo submission\n\nRegistered source: {repo_url}\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: repo-placeholder\ndescription: Placeholder for a registered repository submission.\n---\n\n"
        "The local POC stores repository submissions without cloning them. "
        "Use ZIP upload for full package validation in phase 1.\n",
        encoding="utf-8",
    )


def normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").strip("/")


def is_unsafe_zip_name(name: str) -> bool:
    path = PurePosixPath(name)
    return path.is_absolute() or ".." in path.parts


def detect_package_root(file_names: list[str]) -> str | None:
    if any(name.startswith("skills/") for name in file_names):
        return ""

    roots = {PurePosixPath(name).parts[0] for name in file_names if PurePosixPath(name).parts}
    if len(roots) != 1:
        return None
    root = next(iter(roots))
    if any(name.startswith(f"{root}/skills/") for name in file_names):
        return root
    return None


def detect_skill_names(file_names: list[str], package_root: str) -> list[str]:
    prefix = f"{package_root}/skills/" if package_root else "skills/"
    skill_names = set()
    for name in file_names:
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        parts = PurePosixPath(rest).parts
        if len(parts) >= 2 and parts[1] == "SKILL.md":
            skill_names.add(parts[0])
    return sorted(skill_names)
