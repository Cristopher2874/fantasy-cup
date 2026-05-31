"""Read-only public data endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from services.data_generator.public_data import DEFAULT_PUBLIC_DATA_DIR, PUBLIC_DATA_FILES


router = APIRouter(prefix="/public-data", tags=["public-data"])


@router.get("")
def read_public_data_index() -> dict:
    manifest_path = DEFAULT_PUBLIC_DATA_DIR / "manifest.json"
    manifest = _read_json(manifest_path) if manifest_path.is_file() else None
    return {
        "available": DEFAULT_PUBLIC_DATA_DIR.is_dir(),
        "path": str(DEFAULT_PUBLIC_DATA_DIR),
        "manifest": manifest,
        "files": [filename for filename in PUBLIC_DATA_FILES if (DEFAULT_PUBLIC_DATA_DIR / filename).is_file()],
    }


@router.get("/files/{file_name}")
def read_public_data_file(file_name: str):
    if file_name not in PUBLIC_DATA_FILES:
        raise HTTPException(status_code=404, detail=f"Public data file is not available: {file_name}")

    path = DEFAULT_PUBLIC_DATA_DIR / file_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Public data file has not been generated yet: {file_name}")

    if path.suffix == ".md":
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
    return JSONResponse(_read_json(path))


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Generated public data is not valid JSON: {path.name}") from exc
