"""Defender-context features from 360 freeze-frames.

For every on-ball event covered by a freeze-frame, summarise the defensive
picture at the moment of the action:

- nearest_def:  distance (pitch units) from the ball to the closest opponent
- n_ahead:      opponents goal-side of the ball (x greater than ball x)
- n_cone:       opponents inside the triangle from the ball to both goalposts
                (the bodies actually between the ball and the goal mouth)
"""

import numpy as np
import polars as pl
import psycopg

GOAL_LOW = np.array([120.0, 36.0])
GOAL_HIGH = np.array([120.0, 44.0])


def _in_goal_cone(
    bx: np.ndarray, by: np.ndarray, fx: np.ndarray, fy: np.ndarray
) -> np.ndarray:
    """Vectorised point-in-triangle test for triangle (ball, near post, far post)."""

    def sign(
        ax: np.ndarray, ay: np.ndarray,
        bx_: np.ndarray | float, by_: np.ndarray | float,
        cx: np.ndarray | float, cy: np.ndarray | float,
    ) -> np.ndarray:
        return np.asarray((ax - cx) * (by_ - cy) - (bx_ - cx) * (ay - cy))

    d1 = sign(fx, fy, bx, by, GOAL_LOW[0], GOAL_LOW[1])
    d2 = sign(fx, fy, GOAL_LOW[0], GOAL_LOW[1], GOAL_HIGH[0], GOAL_HIGH[1])
    d3 = sign(fx, fy, GOAL_HIGH[0], GOAL_HIGH[1], bx, by)
    has_neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    has_pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    return np.asarray(~(has_neg & has_pos))


def pressure_features(conn: psycopg.Connection) -> pl.DataFrame:
    """One row per freeze-frame-covered on-ball event."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.event_id::text, e.x, e.y, ff.x AS fx, ff.y AS fy
            FROM events e
            JOIN freeze_frames ff USING (event_id)
            WHERE e.type IN ('Pass', 'Carry', 'Shot', 'Dribble')
              AND e.x IS NOT NULL
              AND NOT ff.teammate        -- opponents only
              AND NOT ff.actor
            """
        )
        rows = cur.fetchall()
    df = pl.DataFrame(rows, schema=["event_id", "x", "y", "fx", "fy"], orient="row")
    bx = df["x"].to_numpy()
    by = df["y"].to_numpy()
    fx = df["fx"].to_numpy()
    fy = df["fy"].to_numpy()
    df = df.with_columns(
        pl.Series("dist", np.hypot(fx - bx, fy - by)),
        pl.Series("ahead", (fx > bx).astype(np.int32)),
        pl.Series("cone", _in_goal_cone(bx, by, fx, fy).astype(np.int32)),
    )
    return df.group_by("event_id").agg(
        pl.col("dist").min().alias("nearest_def"),
        pl.col("ahead").sum().alias("n_ahead"),
        pl.col("cone").sum().alias("n_cone"),
    )
