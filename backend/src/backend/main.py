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
from pydantic import BaseModel, Field

from backend import ask as ask_module
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
def health() -> dict[str, str | bool]:
    return {"status": "ok", "ask_enabled": ask_module.is_enabled()}


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


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/api/teams/{team_id}/ask")
def ask(
    team_id: int,
    body: AskRequest,
    competition_id: Comp = DEFAULT_COMP,
    season_id: Season = DEFAULT_SEASON,
) -> dict[str, Any]:
    import anthropic

    if not ask_module.is_enabled():
        raise HTTPException(
            503, "Q&A is disabled: the server has no ANTHROPIC_API_KEY configured"
        )
    try:
        result = ask_module.ask(team_id, competition_id, season_id, body.question)
    except anthropic.AuthenticationError as exc:
        raise HTTPException(
            401,
            "Anthropic rejected the API key. Check ANTHROPIC_API_KEY in your .env "
            "(it should start with 'sk-ant-') and restart the server.",
        ) from exc
    except anthropic.PermissionDeniedError as exc:
        raise HTTPException(
            403,
            "That API key lacks access to this model, or the account has no credit. "
            "Check billing at console.anthropic.com.",
        ) from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(429, "Rate limited by the Anthropic API — retry shortly.") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(503, "Could not reach the Anthropic API — check connectivity.") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(502, f"Anthropic API error ({exc.status_code}).") from exc
    if result is None:
        raise HTTPException(404, "unknown team in this competition")
    return result


_static = os.environ.get("STATIC_DIR", "")
if _static and Path(_static).is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
