"""Credit every completed pass and carry with the change in expected threat
(dV = V(end) - V(start)) and write the aggregates the dashboard reads:
zone_threat (per team, per 12x8 pitch zone) and player_threat (with a
plain-language scouting note). Run: python -m ml.xt_apply"""

from typing import Any

import numpy as np
import polars as pl
import psycopg

from ml.data import DATABASE_URL
from ml.xt_model import load_model, value_at

ZONE_W = 10.0  # 12 zones along x
ZONE_H = 10.0  # 8 zones along y

LANE_LABELS = {
    0: "the left wing", 1: "the left half-space", 2: "central areas",
    3: "the right half-space", 4: "the right wing",
}


def _credited_actions(conn: psycopg.Connection) -> pl.DataFrame:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.competition_id, m.season_id, e.team_id, e.player_id,
                   e.type, e.x, e.y, e.end_x, e.end_y
            FROM events e JOIN matches m USING (match_id)
            WHERE e.type IN ('Pass', 'Carry')
              AND e.outcome IS NULL         -- completed actions only
              AND e.x IS NOT NULL AND e.end_x IS NOT NULL
              AND e.period <= 4
            """
        )
        names = [d.name for d in cur.description or []]
        df = pl.DataFrame(cur.fetchall(), schema=names, orient="row")
    return df


def compute_credits(df: pl.DataFrame) -> pl.DataFrame:
    model = load_model()
    v_start = value_at(model, df["x"].to_numpy(), df["y"].to_numpy())
    v_end = value_at(model, df["end_x"].to_numpy(), df["end_y"].to_numpy())
    dv = v_end - v_start
    return df.with_columns(
        pl.Series("dv", dv),
        # "Threat created": positive dV only. Negative dV is possession
        # recycling, not danger; summing it would hide progressive players
        # behind their safe back-passes.
        pl.Series("xt", np.maximum(dv, 0.0)),
        (pl.col("x") // ZONE_W).cast(pl.Int32).clip(0, 11).alias("zone_x"),
        (pl.col("y") // ZONE_H).cast(pl.Int32).clip(0, 7).alias("zone_y"),
        (pl.col("y") // 16).cast(pl.Int32).clip(0, 4).alias("lane"),
    )


def write_zone_threat(conn: psycopg.Connection, credits: pl.DataFrame) -> None:
    conn.execute("DELETE FROM zone_threat")
    zones = credits.group_by(
        ["competition_id", "season_id", "team_id", "zone_x", "zone_y"]
    ).agg(pl.col("xt").sum().round(4), pl.len().alias("n_actions"))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO zone_threat VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [tuple(r) for r in zones.iter_rows()],
        )


def _note(row: dict[str, Any], team_rank: int) -> str:
    carry_share = row["xt_carries"] / row["xt_total"] if row["xt_total"] else 0.0
    lane = LANE_LABELS[int(row["top_lane"])]
    if carry_share >= 0.5:
        style = f"ball-carrying threat — {carry_share:.0%} of his xT comes from carries"
    elif carry_share <= 0.25:
        style = f"creates almost entirely with the pass ({1 - carry_share:.0%} of xT)"
    else:
        style = "mixes progressive passing and carrying"
    origin = "deep areas" if row["avg_x"] < 60 else (
        "midfield" if row["avg_x"] < 80 else "the final third"
    )
    rank_txt = {1: "Their top threat creator", 2: "Second-highest threat creator",
                3: "Third-highest threat creator"}.get(
        team_rank, f"No. {team_rank} threat creator"
    )
    return (f"{rank_txt} ({row['xt_per_90']:.2f} xT/90): {style}, "
            f"working mainly from {lane} in {origin}.")


def write_player_threat(conn: psycopg.Connection, credits: pl.DataFrame) -> None:
    conn.execute("DELETE FROM player_threat")
    minutes = {
        (r[0], r[1], r[2], r[3]): r[4]
        for r in conn.execute(
            "SELECT m.competition_id, m.season_id, p.team_id, pm.player_id, "
            "sum(pm.minutes) "
            "FROM player_minutes pm "
            "JOIN players p USING (player_id) "
            "JOIN matches m USING (match_id) "
            "GROUP BY m.competition_id, m.season_id, p.team_id, pm.player_id"
        )
    }
    stats = (
        credits.filter(pl.col("player_id").is_not_null())
        .group_by(["competition_id", "season_id", "team_id", "player_id"])
        .agg(
            pl.col("xt").sum().alias("xt_total"),
            pl.col("xt").filter(pl.col("type") == "Carry").sum().alias("xt_carries"),
            pl.len().alias("n_actions"),
            pl.col("x").filter(pl.col("xt") > 0).mean().alias("avg_x"),
            pl.col("lane")
            .filter(pl.col("xt") > 0)
            .mode()
            .first()
            .alias("top_lane"),
        )
    )
    rows = []
    for _, group in stats.group_by(["competition_id", "season_id", "team_id"]):
        enriched = []
        for r in group.iter_rows(named=True):
            key = (r["competition_id"], r["season_id"], r["team_id"], r["player_id"])
            mins = minutes.get(key)
            if not mins or mins < 1:
                continue
            r["minutes"] = mins
            r["xt_per_90"] = r["xt_total"] / mins * 90
            enriched.append(r)
        ranked = sorted(
            [r for r in enriched if r["minutes"] >= 180], key=lambda r: -r["xt_per_90"]
        )
        rank_of = {r["player_id"]: i + 1 for i, r in enumerate(ranked)}
        for r in enriched:
            note = (
                _note(r, rank_of[r["player_id"]])
                if r["player_id"] in rank_of and r["top_lane"] is not None
                else None
            )
            rows.append((
                r["competition_id"], r["season_id"], r["team_id"], r["player_id"],
                round(r["minutes"], 1), r["n_actions"],
                round(r["xt_total"], 4), round(r["xt_per_90"], 4), note,
            ))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO player_threat VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )


def apply() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        credits = compute_credits(_credited_actions(conn))
        print(f"{credits.height} completed passes/carries credited")
        write_zone_threat(conn, credits)
        write_player_threat(conn, credits)
        conn.commit()
        top = conn.execute(
            "SELECT t.name, p.name, pt.xt_per_90 FROM player_threat pt "
            "JOIN players p USING (player_id) JOIN teams t ON t.team_id = pt.team_id "
            "WHERE pt.minutes >= 270 ORDER BY pt.xt_per_90 DESC LIMIT 10"
        ).fetchall()
        print("top xT/90 (min 270 mins):")
        for r in top:
            print(f"  {r[0]:<14} {r[1]:<40} {r[2]:.3f}")


if __name__ == "__main__":
    apply()
