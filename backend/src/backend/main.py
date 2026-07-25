"""Opposition Scouting API: read-only endpoints over precomputed metrics.

Every team endpoint is scoped to one competition/season (defaults: the
2022 World Cup, so unscoped calls keep working). In production the same
app serves the built frontend (STATIC_DIR), so one process is the whole
deployment.
"""

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import queries

app = FastAPI(title="Opposition Scouting API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

VALID_PHASES = {"all", "open_play", "counter", "goal_kick", "set_piece", "other"}

Comp = Annotated[int, Query(alias="competition_id")]
Season = Annotated[int, Query(alias="season_id")]
DEFAULT_COMP = 43  # FIFA World Cup
DEFAULT_SEASON = 106  # 2022


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/competitions")
def competitions() -> list[dict[str, Any]]:
    return queries.list_competitions()


@app.get("/api/teams")
def teams(
    competition_id: Comp = DEFAULT_COMP, season_id: Season = DEFAULT_SEASON
) -> list[dict[str, Any]]:
    return queries.list_teams(competition_id, season_id)


@app.get("/api/teams/{team_id}/profile")
def profile(
    team_id: int,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> dict[str, Any]:
    result = queries.team_profile(team_id, competition_id, season_id)
    if result is None:
        raise HTTPException(404, "unknown team in this competition")
    return result


@app.get("/api/teams/{team_id}/threat-map")
def threat_map(
    team_id: int,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> list[dict[str, Any]]:
    return queries.threat_map(team_id, competition_id, season_id)


@app.get("/api/teams/{team_id}/pass-network")
def pass_network(
    team_id: int,
    phase: str = Query("all"),
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> dict[str, Any]:
    if phase not in VALID_PHASES:
        raise HTTPException(422, f"phase must be one of {sorted(VALID_PHASES)}")
    return queries.pass_network(team_id, phase, competition_id, season_id)


@app.get("/api/teams/{team_id}/patterns")
def patterns(
    team_id: int,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> list[dict[str, Any]]:
    return queries.patterns(team_id, competition_id, season_id)


@app.get("/api/teams/{team_id}/set-pieces")
def set_pieces(
    team_id: int,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> dict[str, Any]:
    return queries.set_pieces(team_id, competition_id, season_id)


@app.get("/api/teams/{team_id}/watchlist")
def watchlist(
    team_id: int,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> list[dict[str, Any]]:
    return queries.watchlist(team_id, competition_id, season_id)


@app.get("/api/teams/{team_id}/report")
def report(
    team_id: int,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> dict[str, Any]:
    result = queries.report(team_id, competition_id, season_id)
    if result is None:
        raise HTTPException(404, "unknown team in this competition")
    return result


_static = os.environ.get("STATIC_DIR", "")
if _static and Path(_static).is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
