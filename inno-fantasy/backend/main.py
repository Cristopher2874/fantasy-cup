"""FastAPI server entrypoint for the backend."""
from __future__ import annotations

from fastapi import FastAPI

from routes.progress import router as progress_router
from routes.public_data import router as public_data_router
from routes.scores import router as scores_router
from routes.upload import router as upload_router


app = FastAPI(title="Inno Fantasy Backend")
app.include_router(upload_router)
app.include_router(progress_router)
app.include_router(public_data_router)
app.include_router(scores_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
