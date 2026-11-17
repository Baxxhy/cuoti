import os

import uvicorn

from .config import Settings, configuration


def main():
    _, values = configuration()
    for key, value in values.items():
        if value is not None:
            os.environ.setdefault(key, str(value))
    from .main import create_app

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
