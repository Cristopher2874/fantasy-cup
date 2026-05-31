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
from services.rate_limiter import RateLimitMiddleware, build_default_rate_limit, build_rate_limit_rule


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

if CONFIG.get_bool("rate_limit", "enabled", True):
    rate_limit_rules = [
        build_rate_limit_rule(rule)
        for rule in CONFIG.get_config_value("rate_limit", "rules", [])
        if isinstance(rule, dict)
    ]
    default_rate_limit = build_default_rate_limit(CONFIG.get_config_value("rate_limit", "default", {}))
    app.add_middleware(
        RateLimitMiddleware,
        rules=rate_limit_rules,
        default_rule=default_rate_limit,
        client_ip_header=CONFIG.get_str("rate_limit", "client_ip_header", "x-forwarded-for"),
        trust_proxy_headers=CONFIG.get_bool("rate_limit", "trust_proxy_headers", True),
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

    uvicorn.run("main:app", host="127.0.0.1", port=10006, reload=False)
