"""师承智学业务服务。"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(os.getenv("SCZX_ENV_FILE", str(Path(__file__).resolve().parents[1] / ".env")))
except ImportError:
    pass
