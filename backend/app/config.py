import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("CDJ_DB_PATH", BASE_DIR / "data" / "crowdsource_dj.sqlite3"))

# How long a disconnected DJ keeps the booth before it is handed to someone else.
# Covers page refreshes and flaky connections.
DJ_GRACE_SECONDS = float(os.environ.get("CDJ_DJ_GRACE_SECONDS", "15"))

# How long a /voteskip poll stays open.
POLL_SECONDS = float(os.environ.get("CDJ_POLL_SECONDS", "60"))

# Built frontend, served by FastAPI in production.
FRONTEND_DIST = Path(os.environ.get("CDJ_FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))

# Set to "1" in tests to avoid calling out to YouTube.
OFFLINE_MUSIC = os.environ.get("CDJ_OFFLINE_MUSIC") == "1"

CHAT_HISTORY = 200
MAX_CHAT_LENGTH = 500
SUGGESTIONS_TARGET = 15
