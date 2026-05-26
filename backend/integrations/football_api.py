from pathlib import Path
import http.client
import json

from backend.config import settings


class FootballApi:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or settings.source_dir / "api-sports"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, endpoint: str, query: str = "") -> dict:
        if not settings.api_sports_key:
            raise RuntimeError("APISPORTS_KEY is not configured")

        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        if query:
            path = f"{path}?{query}"

        connection = http.client.HTTPSConnection("v3.football.api-sports.io")
        connection.request("GET", path, headers={"x-apisports-key": settings.api_sports_key})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        self.cache_response(endpoint, query, payload)
        return payload

    def cache_response(self, endpoint: str, query: str, payload: dict) -> None:
        safe_name = endpoint.strip("/").replace("/", "-") or "root"
        if query:
            safe_name = f"{safe_name}-{abs(hash(query))}"
        (self.cache_dir / f"{safe_name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
