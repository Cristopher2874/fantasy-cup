from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routes import organizer, public, teams
from backend.services.state_store import store


app = FastAPI(title="AI Agent Fantasy World Cup", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    store.ensure()


app.include_router(public.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(organizer.router, prefix="/api")

app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
