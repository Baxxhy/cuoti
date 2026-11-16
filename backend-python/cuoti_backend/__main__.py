import uvicorn

from .config import Settings
from .main import create_app


def main():
    settings = Settings.load()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
