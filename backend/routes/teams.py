from pathlib import Path
import shutil

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.package_validator import (
    create_repo_snapshot,
    extract_zip_snapshot,
    validate_repo_url,
    validate_zip_package,
)
from backend.services.state_store import hash_token, make_token, store, utc_now

router = APIRouter(tags=["teams"])


class RegisterTeamRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    members: list[str] = Field(default_factory=list)
    submission_method: str = "zip"
    repo_url: str | None = None


class LoginRequest(BaseModel):
    token: str
    team_id: str | None = None
    name: str | None = None


class RepoSubmissionRequest(BaseModel):
    repo_url: str


@router.post("/teams/register")
def register_team(payload: RegisterTeamRequest) -> dict:
    teams = store.read("teams")
    if any(team["name"].lower() == payload.name.lower() for team in teams):
        raise HTTPException(status_code=409, detail="Team name already exists")

    team_id = store.next_id("TEAM", "teams")
    token = make_token()
    team = {
        "id": team_id,
        "name": payload.name,
        "members": payload.members,
        "token_hash": hash_token(token),
        "submission_method": payload.submission_method,
        "repo_url": payload.repo_url,
        "created_at": utc_now(),
    }
    store.append("teams", team)

    return {"team": safe_team(team), "token": token}


@router.post("/team/login")
def login(payload: LoginRequest) -> dict:
    team = authenticate(payload.token, payload.team_id, payload.name)
    return {"team": safe_team(team)}


@router.get("/team/me")
def team_me(
    x_team_token: str = Header(alias="X-Team-Token"),
    x_team_id: str | None = Header(default=None, alias="X-Team-Id"),
) -> dict:
    team = authenticate(x_team_token, x_team_id, None)
    return {
        "team": safe_team(team),
        "latest_snapshot": latest_snapshot(team["id"]),
    }


@router.post("/team/submission/zip")
async def upload_zip(
    file: UploadFile = File(...),
    x_team_token: str = Header(alias="X-Team-Token"),
    x_team_id: str | None = Header(default=None, alias="X-Team-Id"),
) -> dict:
    team = authenticate(x_team_token, x_team_id, None)
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a ZIP file")

    submission_id = store.next_id("SUB", "submissions")
    upload_dir = settings.uploads_dir / team["id"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{submission_id}-{Path(file.filename).name}"

    with upload_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    validation = validate_zip_package(upload_path)
    submission = {
        "id": submission_id,
        "team_id": team["id"],
        "source": "zip",
        "path": str(upload_path.relative_to(settings.project_root)),
        "accepted": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "created_at": utc_now(),
    }
    store.append("submissions", submission)

    snapshot = None
    if validation["valid"]:
        snapshot = create_snapshot(team["id"], submission_id, "zip", upload_path, validation)

    return {"submission": submission, "snapshot": snapshot}


@router.post("/team/submission/repo")
def register_repo_submission(
    payload: RepoSubmissionRequest,
    x_team_token: str = Header(alias="X-Team-Token"),
    x_team_id: str | None = Header(default=None, alias="X-Team-Id"),
) -> dict:
    team = authenticate(x_team_token, x_team_id, None)
    validation = validate_repo_url(payload.repo_url)
    submission_id = store.next_id("SUB", "submissions")
    submission = {
        "id": submission_id,
        "team_id": team["id"],
        "source": "repo",
        "repo_url": payload.repo_url,
        "accepted": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "created_at": utc_now(),
    }
    store.append("submissions", submission)

    snapshot = None
    if validation["valid"]:
        snapshot = create_snapshot(team["id"], submission_id, "repo", None, validation, payload.repo_url)
        team["repo_url"] = payload.repo_url
        team["submission_method"] = "repo"
        store.update("teams", team["id"], team)

    return {"submission": submission, "snapshot": snapshot}


@router.get("/team/submissions")
def get_team_submissions(
    x_team_token: str = Header(alias="X-Team-Token"),
    x_team_id: str | None = Header(default=None, alias="X-Team-Id"),
) -> dict:
    team = authenticate(x_team_token, x_team_id, None)
    submissions = [item for item in store.read("submissions") if item["team_id"] == team["id"]]
    snapshots = [item for item in store.read("snapshots") if item["team_id"] == team["id"]]
    submissions.sort(key=lambda item: item["created_at"], reverse=True)
    snapshots.sort(key=lambda item: item["created_at"], reverse=True)
    return {"submissions": submissions, "snapshots": snapshots}


@router.get("/team/runs")
def get_team_runs(
    x_team_token: str = Header(alias="X-Team-Token"),
    x_team_id: str | None = Header(default=None, alias="X-Team-Id"),
) -> dict:
    team = authenticate(x_team_token, x_team_id, None)
    runs = [item for item in store.read("runs") if item["team_id"] == team["id"]]
    runs.sort(key=lambda item: item["created_at"], reverse=True)
    return {"runs": runs}


@router.get("/team/runs/{run_id}")
def get_team_run(
    run_id: str,
    x_team_token: str = Header(alias="X-Team-Token"),
    x_team_id: str | None = Header(default=None, alias="X-Team-Id"),
) -> dict:
    team = authenticate(x_team_token, x_team_id, None)
    run = store.find_by_id("runs", run_id)
    if not run or run["team_id"] != team["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run": run}


def authenticate(token: str, team_id: str | None, name: str | None) -> dict:
    token_hash = hash_token(token)
    for team in store.read("teams"):
        id_matches = team_id and team["id"] == team_id
        name_matches = name and team["name"].lower() == name.lower()
        fallback_match = not team_id and not name
        if (id_matches or name_matches or fallback_match) and team["token_hash"] == token_hash:
            return team
    raise HTTPException(status_code=401, detail="Invalid team token")


def create_snapshot(
    team_id: str,
    submission_id: str,
    source: str,
    upload_path: Path | None,
    validation: dict,
    repo_url: str | None = None,
) -> dict:
    snapshot_id = store.next_id("SNP", "snapshots")
    snapshot_dir = settings.snapshots_dir / team_id / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if source == "zip" and upload_path:
        extract_zip_snapshot(upload_path, snapshot_dir, validation["package_root"])
    elif source == "repo":
        create_repo_snapshot(snapshot_dir, repo_url or "")

    snapshot = {
        "id": snapshot_id,
        "team_id": team_id,
        "submission_id": submission_id,
        "matchday_id": None,
        "source": source,
        "repo_url": repo_url,
        "path": str(snapshot_dir.relative_to(settings.project_root)),
        "accepted": True,
        "errors": [],
        "warnings": validation["warnings"],
        "created_at": utc_now(),
    }
    store.append("snapshots", snapshot)
    return snapshot


def latest_snapshot(team_id: str) -> dict | None:
    snapshots = [
        item
        for item in store.read("snapshots")
        if item["team_id"] == team_id and item.get("accepted")
    ]
    snapshots.sort(key=lambda item: item["created_at"], reverse=True)
    return snapshots[0] if snapshots else None


def safe_team(team: dict) -> dict:
    return {key: value for key, value in team.items() if key != "token_hash"}
