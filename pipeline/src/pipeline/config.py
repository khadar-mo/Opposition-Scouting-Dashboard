"""Central configuration for the ingestion pipeline."""

import os
from pathlib import Path

# Competitions ingested into the dashboard, as (competition_id, season_id).
COMPETITIONS: list[tuple[int, int]] = [
    (43, 106),  # FIFA World Cup 2022
    (55, 282),  # UEFA Euro 2024
]

OPEN_DATA_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("SCOUT_DATA_DIR", REPO_ROOT / "data" / "raw"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://scout:scout@localhost:5432/scouting"
)
