"""FastAPI server entrypoint for the backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config.config_provider import GlobalConfigProvider
from routes.progress import router as progress_router
from routes.public_data import router as public_data_router
from routes.scores import router as scores_router
from routes.upload import router as upload_router


CONFIG = GlobalConfigProvider()


def _list_config(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    item = str(value).strip()
    return [item] if item else []


app = FastAPI(
    title="Inno Fantasy Backend",
    root_path=CONFIG.get_str("server", "root_path", ""),
)

trusted_hosts = _list_config(CONFIG.get_config_value("server", "trusted_hosts", []))
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

cors_allowed_origins = _list_config(CONFIG.get_config_value("server", "cors_allowed_origins", []))
if cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_credentials=CONFIG.get_bool("server", "cors_allow_credentials", False),
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
