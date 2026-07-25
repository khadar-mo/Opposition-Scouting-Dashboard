"""Normalise raw StatsBomb JSON into Postgres.

Full reload each run: analytic truth lives in the raw files, so the simplest
correct behaviour is truncate-and-reload rather than incremental merging.
"""

import json
from pathlib import Path
from typing import Any

import polars as pl
import psycopg

from pipeline.config import COMPETITIONS, DATA_DIR
from pipeline.db import connect
from pipeline.download import matches_path

# Keys under which StatsBomb nests the type-specific event payload.
_PAYLOAD_KEYS = {
    "pass", "shot", "carry", "dribble", "duel", "clearance", "interception",
    "ball_receipt", "ball_recovery", "block", "foul_committed", "foul_won",
    "goalkeeper", "substitution", "miscontrol", "injury_stoppage",
    "bad_behaviour", "half_start", "player_off", "50_50",
}

_EVENT_COLUMNS = [
    "event_id", "match_id", "idx", "period", "timestamp_s", "minute", "second",
    "possession", "possession_team_id", "play_pattern", "team_id", "player_id",
    "position", "type", "x", "y", "end_x", "end_y", "outcome", "recipient_id",
    "xg", "under_pressure", "duration", "attrs",
]

_EVENT_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "event_id": pl.Utf8, "match_id": pl.Int64, "idx": pl.Int64, "period": pl.Int64,
    "timestamp_s": pl.Float64, "minute": pl.Int64, "second": pl.Int64,
    "possession": pl.Int64, "possession_team_id": pl.Int64, "play_pattern": pl.Utf8,
    "team_id": pl.Int64, "player_id": pl.Int64, "position": pl.Utf8, "type": pl.Utf8,
    "x": pl.Float64, "y": pl.Float64, "end_x": pl.Float64, "end_y": pl.Float64,
    "outcome": pl.Utf8, "recipient_id": pl.Int64, "xg": pl.Float64,
    "under_pressure": pl.Boolean, "duration": pl.Float64, "attrs": pl.Utf8,
}


def _timestamp_to_seconds(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _extract_event(ev: dict[str, Any], match_id: int) -> dict[str, Any]:
    payload_key = next((k for k in ev if k in _PAYLOAD_KEYS), None)
    payload = ev.get(payload_key) if payload_key else None

    end_loc = (payload or {}).get("end_location")
    outcome = (payload or {}).get("outcome", {}).get("name") if payload else None
    recipient = (payload or {}).get("recipient", {}).get("id") if payload else None
    loc = ev.get("location")
    return {
        "event_id": ev["id"],
        "match_id": match_id,
        "idx": ev["index"],
        "period": ev["period"],
        "timestamp_s": _timestamp_to_seconds(ev["timestamp"]),
        "minute": ev["minute"],
        "second": ev["second"],
        "possession": ev["possession"],
        "possession_team_id": ev["possession_team"]["id"],
        "play_pattern": ev["play_pattern"]["name"],
        "team_id": ev["team"]["id"],
        "player_id": ev.get("player", {}).get("id"),
        "position": ev.get("position", {}).get("name"),
        "type": ev["type"]["name"],
        "x": loc[0] if loc else None,
        "y": loc[1] if loc else None,
        "end_x": end_loc[0] if end_loc else None,
        "end_y": end_loc[1] if end_loc else None,
        "outcome": outcome,
        "recipient_id": recipient,
        "xg": (payload or {}).get("statsbomb_xg"),
        "under_pressure": bool(ev.get("under_pressure", False)),
        "duration": ev.get("duration"),
        "attrs": json.dumps(payload) if payload is not None else None,
    }


def load_events_frame(events_path: Path, match_id: int) -> pl.DataFrame:
    """Parse one raw events file into a typed Polars frame."""
    raw = json.loads(events_path.read_text())
    rows = [_extract_event(ev, match_id) for ev in raw]
    return pl.DataFrame(rows, schema=_EVENT_SCHEMA, orient="row").sort("idx")


def _copy_frame(conn: psycopg.Connection, table: str, columns: list[str], df: pl.DataFrame) -> None:
    with conn.cursor() as cur, cur.copy(
        f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    ) as copy:
        for row in df.iter_rows():
            copy.write_row(row)


def _ingest_metadata(
    conn: psycopg.Connection, seasons: list[tuple[int, int, list[dict[str, Any]]]]
) -> None:
    teams: dict[int, str] = {}
    for comp_id, season_id, matches in seasons:
        comp = matches[0]
        conn.execute(
            "INSERT INTO competitions VALUES (%s, %s, %s, %s)",
            (comp_id, season_id, comp["competition"]["competition_name"],
             comp["season"]["season_name"]),
        )
        for m in matches:
            teams[m["home_team"]["home_team_id"]] = m["home_team"]["home_team_name"]
            teams[m["away_team"]["away_team_id"]] = m["away_team"]["away_team_name"]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO teams VALUES (%s, %s)", list(teams.items()))
        cur.executemany(
            """INSERT INTO matches (match_id, competition_id, season_id, match_date,
                                    stage, home_team_id, away_team_id, home_score, away_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (m["match_id"], comp_id, season_id, m["match_date"],
                 m["competition_stage"]["name"], m["home_team"]["home_team_id"],
                 m["away_team"]["away_team_id"], m["home_score"], m["away_score"])
                for comp_id, season_id, matches in seasons
                for m in matches
            ],
        )


def _ingest_players(conn: psycopg.Connection, match_ids: list[int]) -> None:
    players: dict[int, tuple[int, str, str | None, int, int | None, str | None]] = {}
    for mid in match_ids:
        lineup_file = DATA_DIR / "lineups" / f"{mid}.json"
        for team in json.loads(lineup_file.read_text()):
            for p in team["lineup"]:
                positions = p.get("positions", [])
                position = positions[0]["position"] if positions else None
                existing = players.get(p["player_id"])
                # Keep the first row that has a position; lineups repeat per match.
                if existing is None or (existing[5] is None and position):
                    players[p["player_id"]] = (
                        p["player_id"], p["player_name"], p.get("player_nickname"),
                        team["team_id"], p.get("jersey_number"), position,
                    )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO players VALUES (%s, %s, %s, %s, %s, %s)",
            list(players.values()),
        )


def _ingest_freeze_frames(conn: psycopg.Connection, match_id: int) -> int:
    path = DATA_DIR / "three-sixty" / f"{match_id}.json"
    if not path.exists():
        return 0
    known = {
        str(r[0])
        for r in conn.execute(
            "SELECT event_id FROM events WHERE match_id = %s", (match_id,)
        )
    }
    rows = []
    for frame in json.loads(path.read_text()):
        if frame["event_uuid"] not in known:
            continue
        for p in frame.get("freeze_frame") or []:
            rows.append((
                frame["event_uuid"], p["teammate"], p["actor"], p["keeper"],
                p["location"][0], p["location"][1],
            ))
    if rows:
        with conn.cursor() as cur, cur.copy(
            "COPY freeze_frames (event_id, teammate, actor, keeper, x, y) FROM STDIN"
        ) as copy:
            for row in rows:
                copy.write_row(row)
    return len(rows)


def ingest_all(limit: int | None = None) -> None:
    seasons: list[tuple[int, int, list[dict[str, Any]]]] = []
    for comp_id, season_id in COMPETITIONS:
        matches = json.loads(matches_path(comp_id, season_id).read_text())
        matches.sort(key=lambda m: m["match_id"])
        if limit:
            matches = matches[:limit]
        seasons.append((comp_id, season_id, matches))
    match_ids = [m["match_id"] for _, _, ms in seasons for m in ms]

    with connect() as conn:
        conn.execute(
            "TRUNCATE competitions, teams, players, matches, events, freeze_frames, "
            "sequences, zone_threat, pass_edges, pass_nodes, player_threat, "
            "set_pieces, pattern_clusters, team_patterns CASCADE"
        )
        _ingest_metadata(conn, seasons)
        _ingest_players(conn, match_ids)
        total_events = 0
        for i, mid in enumerate(match_ids, 1):
            df = load_events_frame(DATA_DIR / "events" / f"{mid}.json", mid)
            _copy_frame(conn, "events", _EVENT_COLUMNS, df)
            n_frames = _ingest_freeze_frames(conn, mid)
            total_events += df.height
            print(f"[{i}/{len(match_ids)}] match {mid}: {df.height} events, "
                  f"{n_frames} freeze-frame players", flush=True)
        conn.commit()
    print(f"ingested {len(match_ids)} matches, {total_events} events")


def verify(match_id: int) -> None:
    """Compare DB contents against the raw JSON for one match."""
    raw = json.loads((DATA_DIR / "events" / f"{match_id}.json").read_text())
    with connect() as conn:
        row = conn.execute(
            "SELECT count(*) FROM events WHERE match_id = %s", (match_id,)
        ).fetchone()
        shots = conn.execute(
            "SELECT count(*), coalesce(sum(xg), 0) FROM events "
            "WHERE match_id = %s AND type = 'Shot'", (match_id,)
        ).fetchone()
        pass_row = conn.execute(
            "SELECT count(*) FROM events WHERE match_id = %s AND type = 'Pass' "
            "AND end_x IS NOT NULL", (match_id,)
        ).fetchone()
    assert row is not None and shots is not None and pass_row is not None
    db_n, passes = row[0], pass_row[0]
    raw_shots = [e for e in raw if e["type"]["name"] == "Shot"]
    raw_xg = sum(e["shot"]["statsbomb_xg"] for e in raw_shots)
    assert db_n == len(raw), f"event count mismatch: db={db_n} raw={len(raw)}"
    assert shots[0] == len(raw_shots), "shot count mismatch"
    assert abs(shots[1] - raw_xg) < 1e-6, "xG sum mismatch"
    print(f"match {match_id}: {db_n} events, {shots[0]} shots (xG {shots[1]:.2f}), "
          f"{passes} located passes — matches raw JSON ✓")
