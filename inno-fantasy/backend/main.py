"""FastAPI server entrypoint for the backend."""
from __future__ import annotations

from fastapi import FastAPI

from backend.routes.progress import router as progress_router
from backend.routes.upload import router as upload_router


app = FastAPI(title="Inno Fantasy Backend")
app.include_router(upload_router)
app.include_router(progress_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
