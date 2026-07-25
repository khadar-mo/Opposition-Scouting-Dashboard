"""Opposition Scouting backend.

Loads a repo-root .env (if present) before any submodule reads the
environment, so `uv run uvicorn backend.main:app` picks up optional settings
like ANTHROPIC_API_KEY and DATABASE_URL without exporting them by hand.
Real environment variables always take precedence over the file.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")
