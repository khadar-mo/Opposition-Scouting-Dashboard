"""Opposition Scouting API: read-only endpoints over precomputed metrics.

In production the same app serves the built frontend (STATIC_DIR), so one
process is the whole deployment.
"""

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import queries

app = FastAPI(title="Opposition Scouting API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

VALID_PHASES = {"all", "open_play", "counter", "goal_kick", "set_piece", "other"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/teams")
def teams() -> list[dict[str, Any]]:
    return queries.list_teams()


@app.get("/api/teams/{team_id}/profile")
def profile(team_id: int) -> dict[str, Any]:
    result = queries.team_profile(team_id)
    if result is None:
        raise HTTPException(404, "unknown team")
    return result


@app.get("/api/teams/{team_id}/threat-map")
def threat_map(team_id: int) -> list[dict[str, Any]]:
    return queries.threat_map(team_id)


@app.get("/api/teams/{team_id}/pass-network")
def pass_network(
    team_id: int, phase: str = Query("all")
) -> dict[str, Any]:
    if phase not in VALID_PHASES:
        raise HTTPException(422, f"phase must be one of {sorted(VALID_PHASES)}")
    return queries.pass_network(team_id, phase)


@app.get("/api/teams/{team_id}/patterns")
def patterns(team_id: int) -> list[dict[str, Any]]:
    return queries.patterns(team_id)


@app.get("/api/teams/{team_id}/set-pieces")
def set_pieces(team_id: int) -> dict[str, Any]:
    return queries.set_pieces(team_id)


@app.get("/api/teams/{team_id}/watchlist")
def watchlist(team_id: int) -> list[dict[str, Any]]:
    return queries.watchlist(team_id)


@app.get("/api/teams/{team_id}/report")
def report(team_id: int) -> dict[str, Any]:
    result = queries.report(team_id)
    if result is None:
        raise HTTPException(404, "unknown team")
    return result


_static = os.environ.get("STATIC_DIR", "")
if _static and Path(_static).is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
