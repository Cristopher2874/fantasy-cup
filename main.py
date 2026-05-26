import uvicorn

from backend.config import settings


def main():
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    main()
