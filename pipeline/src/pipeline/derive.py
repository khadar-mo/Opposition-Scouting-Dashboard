"""Derived-metric tables, computed once at ingestion time.

Everything the API serves comes from these tables; nothing is computed
per-request. StatsBomb pitch: 120x80, every team attacks left-to-right
(x -> 120), y = 0 is the attacking team's LEFT touchline (verified against
full-back average positions in the data).
"""

import json
import math
from itertools import pairwise
from typing import Any, cast

import polars as pl
import psycopg

from pipeline.config import DATA_DIR
from pipeline.db import connect

ON_BALL_TYPES = ("Pass", "Carry", "Shot", "Dribble")

# StatsBomb play_pattern -> the phase filter an analyst actually uses.
PHASE_MAP = {
    "Regular Play": "open_play",
    "From Counter": "counter",
    "From Goal Kick": "goal_kick",
    "From Corner": "set_piece",
    "From Free Kick": "set_piece",
    "From Throw In": "set_piece",
    "From Kick Off": "other",
    "From Keeper": "other",
    "Other": "other",
}

LANES = ["wide_left", "left_halfspace", "central", "right_halfspace", "wide_right"]


def lane_of(y: float) -> int:
    """5 vertical lanes of 16 units each; index into LANES."""
    return min(4, int(y // 16))


def _events_frame(conn: psycopg.Connection) -> pl.DataFrame:
    cols = (
        "e.event_id::text, e.match_id, m.competition_id, m.season_id, e.idx, "
        "e.period, e.timestamp_s, e.minute, e.possession, e.possession_team_id, "
        "e.play_pattern, e.team_id, e.player_id, e.position, e.type, "
        "e.x, e.y, e.end_x, e.end_y, e.outcome, e.recipient_id, e.xg"
    )
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {cols} FROM events e JOIN matches m USING (match_id) "
            "ORDER BY e.match_id, e.idx"
        )
        names = [d.name for d in cur.description or []]
        names[0] = "event_id"
        rows = cur.fetchall()
    return pl.DataFrame(rows, schema=names, orient="row")


# ---------------------------------------------------------------- sequences

def _sequence_features(seq: pl.DataFrame) -> dict[str, Any] | None:
    """Feature vector for one possession's on-ball located events."""
    on_ball = seq.filter(pl.col("type").is_in(ON_BALL_TYPES) & pl.col("x").is_not_null())
    if on_ball.height < 2:
        return None
    xs: list[float] = on_ball["x"].to_list()
    ys: list[float] = on_ball["y"].to_list()
    start_x, start_y, end_x, end_y = xs[0], ys[0], xs[-1], ys[-1]
    points = pairwise(zip(xs, ys, strict=True))
    path = sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in points)
    ts_max = cast(float, on_ball["timestamp_s"].max())
    ts_min = cast(float, on_ball["timestamp_s"].min())
    duration = max(0.1, ts_max - ts_min)

    entry_lane = -1
    for i in range(1, len(xs)):
        if xs[i] >= 80 and xs[i - 1] < 80:
            entry_lane = lane_of(ys[i])
            break
    if entry_lane == -1 and xs[0] >= 80:
        entry_lane = lane_of(ys[0])

    return {
        "start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y,
        "progression": end_x - start_x,
        "max_x": max(xs),
        "n_actions": on_ball.height,
        "duration_s": round(duration, 2),
        "tempo": round(on_ball.height / duration, 3),
        "directness": round((end_x - start_x) / path, 3) if path > 0 else 0.0,
        "width_mean": round(sum(ys) / len(ys), 2),
        "width_sd": round(cast(float, pl.Series(ys).std()) or 0.0, 2),
        "entered_final_third": int(max(xs) >= 80),
        "entry_lane": entry_lane,
    }


def derive_sequences(conn: psycopg.Connection, events: pl.DataFrame) -> int:
    conn.execute("DELETE FROM sequences")
    rows = []
    for (match_id, possession), seq in events.group_by(
        ["match_id", "possession"], maintain_order=True
    ):
        team_id = seq["possession_team_id"][0]
        own = seq.filter(pl.col("team_id") == team_id)
        feats = _sequence_features(own)
        if feats is None:
            continue
        shots = own.filter(pl.col("type") == "Shot")
        rows.append((
            match_id, team_id, possession,
            feats["start_x"], feats["start_y"], feats["end_x"], feats["end_y"],
            feats["n_actions"], feats["duration_s"],
            shots.height > 0,
            float(shots["xg"].sum()) if shots.height else None,
            own["play_pattern"][0],
            json.dumps(feats),
        ))
    with conn.cursor() as cur, cur.copy(
        "COPY sequences (match_id, team_id, possession, start_x, start_y, end_x, "
        "end_y, n_events, duration_s, ended_in_shot, xg, play_pattern, features) "
        "FROM STDIN"
    ) as copy:
        for row in rows:
            copy.write_row(row)
    return len(rows)


# ------------------------------------------------------------- pass network

def derive_pass_network(conn: psycopg.Connection, events: pl.DataFrame) -> None:
    conn.execute("DELETE FROM pass_edges")
    conn.execute("DELETE FROM pass_nodes")
    passes = events.filter(
        (pl.col("type") == "Pass")
        & pl.col("outcome").is_null()  # StatsBomb: null outcome == completed
        & pl.col("recipient_id").is_not_null()
    ).with_columns(
        pl.col("play_pattern").replace_strict(PHASE_MAP, default="other").alias("phase")
    )
    both = pl.concat([passes, passes.with_columns(pl.lit("all").alias("phase"))])
    comp_cols = ["competition_id", "season_id"]

    edges = both.group_by([*comp_cols, "team_id", "phase", "player_id", "recipient_id"]).len()
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO pass_edges VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [tuple(r) for r in edges.iter_rows()],
        )

    # Node position = average location of a player's on-ball involvements
    # (pass origins + receipt locations) in that phase.
    origins = both.select(*comp_cols, "team_id", "phase", pl.col("player_id"), "x", "y")
    receipts = both.select(
        *comp_cols, "team_id", "phase", pl.col("recipient_id").alias("player_id"),
        pl.col("end_x").alias("x"), pl.col("end_y").alias("y"),
    )
    touches = pl.concat([origins, receipts]).drop_nulls()
    nodes = touches.group_by([*comp_cols, "team_id", "phase", "player_id"]).agg(
        pl.col("x").mean().round(2), pl.col("y").mean().round(2), pl.len().alias("n")
    )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO pass_nodes VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [tuple(r) for r in nodes.iter_rows()],
        )


# --------------------------------------------------------------- set pieces

def _corner_zone(end_x: float, y_mirrored: float, corner_y: float) -> str:
    """Delivery zone; y_mirrored is normalised so the corner is taken at y=0."""
    if math.hypot(120 - end_x, y_mirrored - 0) < 15:
        return "short"
    if end_x < 102:
        return "out_of_box"
    if end_x < 108:
        return "edge_of_box"
    if y_mirrored < 37:
        return "near_post"
    if y_mirrored <= 43:
        return "central"
    return "far_post"


_TOUCH_TYPES = (
    "Ball Receipt*", "Clearance", "Duel", "Shot", "Goal Keeper", "Block",
    "Interception", "Miscontrol", "Ball Recovery",
)


def derive_set_pieces(conn: psycopg.Connection, events: pl.DataFrame) -> int:
    conn.execute("DELETE FROM set_pieces")
    corners = events.filter(
        (pl.col("type") == "Pass") & (pl.col("play_pattern") == "From Corner")
    )
    # A corner kick itself: pass taken from a corner arc.
    corners = corners.filter(
        (pl.col("x") > 118) & ((pl.col("y") < 2) | (pl.col("y") > 78))
    )
    rows = []
    for c in corners.iter_rows(named=True):
        side = "left" if c["y"] < 40 else "right"
        end_x, end_y = c["end_x"], c["end_y"]
        if end_x is None:
            continue
        y_m = end_y if side == "left" else 80 - end_y
        # First contact: next touch-type event in the match within 10 seconds.
        nxt = events.filter(
            (pl.col("match_id") == c["match_id"])
            & (pl.col("idx") > c["idx"])
            & (pl.col("period") == c["period"])
            & (pl.col("timestamp_s") <= c["timestamp_s"] + 10)
            & pl.col("type").is_in(_TOUCH_TYPES)
            & pl.col("x").is_not_null()
        ).sort("idx").head(1)
        fc = nxt.row(0, named=True) if nxt.height else None
        # First-contact coordinates in the corner-taking team's attacking frame.
        fc_x = fc_y = None
        fc_team = fc_player = None
        if fc is not None:
            fc_team, fc_player = fc["team_id"], fc["player_id"]
            fc_x, fc_y = fc["x"], fc["y"]
            if fc_team != c["team_id"] and fc_x is not None:
                fc_x, fc_y = 120 - fc_x, 80 - fc_y
        shot = events.filter(
            (pl.col("match_id") == c["match_id"])
            & (pl.col("possession") == c["possession"])
            & (pl.col("team_id") == c["team_id"])
            & (pl.col("type") == "Shot")
        )
        attrs = conn.execute(
            "SELECT attrs->'technique'->>'name' FROM events WHERE event_id = %s",
            (c["event_id"],),
        ).fetchone()
        rows.append((
            c["event_id"], c["match_id"], c["team_id"], "corner", side,
            end_x, end_y, _corner_zone(end_x, y_m, c["y"]),
            attrs[0] if attrs else None,
            fc_team, fc_player, fc_x, fc_y, shot.height > 0,
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO set_pieces VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )
    return len(rows)


# ------------------------------------------------------------ player minutes

def derive_player_minutes(conn: psycopg.Connection, events: pl.DataFrame) -> None:
    """Minutes on pitch, on the event clock (stoppage time included).

    The lineup files' position stints are unreliable (overlapping/wrapped
    clocks in extra-time matches), so entries and exits are taken from the
    events: starters enter at 0', subs at the substitution event, exits at
    substitution-off or red card, otherwise the match's final event minute.
    """
    conn.execute("DELETE FROM player_minutes")

    # Exclude the penalty shootout (period 5) from the playing clock.
    match_end = {
        r[0]: r[1]
        for r in events.filter(pl.col("period") <= 4)
        .group_by("match_id")
        .agg(pl.col("minute").max())
        .iter_rows()
    }
    on: dict[tuple[int, int], int] = {}
    off: dict[tuple[int, int], int] = {}
    for mid, minute, off_player, on_player in conn.execute(
        "SELECT match_id, minute, player_id, (attrs->'replacement'->>'id')::int "
        "FROM events WHERE type = 'Substitution'"
    ):
        off[(mid, off_player)] = minute
        on[(mid, on_player)] = minute
    for mid, minute, player in conn.execute(
        "SELECT match_id, minute, player_id FROM events "
        "WHERE attrs->'card'->>'name' IN ('Red Card', 'Second Yellow')"
    ):
        off[(mid, player)] = minute
    known_players = {r[0] for r in conn.execute("SELECT player_id FROM players")}
    for mid in match_end:
        lineup = json.loads((DATA_DIR / "lineups" / f"{mid}.json").read_text())
        for team in lineup:
            for p in team["lineup"]:
                stints = p.get("positions", [])
                started = any(
                    s["from"] == "00:00" and s.get("from_period") == 1 for s in stints
                )
                if started:
                    on.setdefault((mid, p["player_id"]), 0)
    rows = [
        (mid, pid, max(1, off.get((mid, pid), match_end[mid]) - start))
        for (mid, pid), start in on.items()
        if pid in known_players
    ]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO player_minutes VALUES (%s, %s, %s)", rows)


def derive_all(skip_xt: bool = False) -> None:
    with connect() as conn:
        events = _events_frame(conn)
        print(f"loaded {events.height} events")
        n_seq = derive_sequences(conn, events)
        print(f"sequences: {n_seq}")
        derive_pass_network(conn, events)
        print("pass network derived")
        n_sp = derive_set_pieces(conn, events)
        print(f"set pieces: {n_sp} corners")
        derive_player_minutes(conn, events)
        print("player minutes derived")
        conn.commit()
    if not skip_xt:
        print("NOTE: zone_threat / player_threat are written by the ml package "
              "(python -m ml.xt_apply) once the xT model is trained.")
