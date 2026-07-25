"""Training data for the expected-threat model.

Each sample is an on-ball action location; the (soft) label is the xG the
possession produces within the next K on-ball actions by the same team,
capped at 1. Learning V(position) this way grounds "threat" in real shot
outcomes rather than hand-tuned grids.
"""

import os
from dataclasses import dataclass

import numpy as np
import polars as pl
import psycopg

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://scout:scout@localhost:5432/scouting"
)

K_ACTIONS = 5
ON_BALL = ("Pass", "Carry", "Shot", "Dribble")


@dataclass
class Dataset:
    features: np.ndarray  # (n, 4): x, y, dist_to_goal, angle_to_goal (normalised)
    labels: np.ndarray  # (n,) soft labels in [0, 1]
    match_ids: np.ndarray  # (n,) for match-level splits


def featurize(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Position features. Goal centre is (120, 40) in StatsBomb coordinates."""
    dx = 120.0 - x
    dy = 40.0 - y
    dist = np.sqrt(dx**2 + dy**2)
    angle = np.abs(np.arctan2(dy, np.maximum(dx, 1e-6)))
    return np.stack(
        [x / 120.0, y / 80.0, dist / 144.0, angle / np.pi], axis=1
    ).astype(np.float32)


def load_actions() -> pl.DataFrame:
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT match_id, possession, team_id, idx, type, x, y, end_x, end_y,
                   coalesce(xg, 0) AS xg, outcome
            FROM events
            WHERE type = ANY(%s) AND x IS NOT NULL
            ORDER BY match_id, idx
            """,
            (list(ON_BALL),),
        )
        names = [d.name for d in cur.description or []]
        rows = cur.fetchall()
    return pl.DataFrame(rows, schema=names, orient="row")


def build_dataset(actions: pl.DataFrame, k: int = K_ACTIONS) -> Dataset:
    """Soft label per action: capped sum of team xG over the next k actions
    of the same possession (inclusive of the action itself)."""
    feats: list[np.ndarray] = []
    labels: list[float] = []
    matches: list[int] = []
    for (_, _, _), group in actions.group_by(
        ["match_id", "possession", "team_id"], maintain_order=True
    ):
        xs = group["x"].to_numpy()
        ys = group["y"].to_numpy()
        xgs = group["xg"].to_numpy()
        mid = int(group["match_id"][0])
        n = len(xs)
        # Rolling forward-window sum of xG over the next k actions.
        cum = np.concatenate([[0.0], np.cumsum(xgs)])
        for i in range(n):
            label = min(1.0, float(cum[min(n, i + k)] - cum[i]))
            feats.append(np.array([xs[i], ys[i]]))
            labels.append(label)
            matches.append(mid)
    xy = np.array(feats)
    return Dataset(
        features=featurize(xy[:, 0], xy[:, 1]),
        labels=np.array(labels, dtype=np.float32),
        match_ids=np.array(matches),
    )


def split_by_match(
    ds: Dataset, val_fraction: float = 0.2, seed: int = 7
) -> tuple[Dataset, Dataset]:
    """Match-level split: all actions of a match land on the same side, so
    validation measures generalisation to unseen games, not memorised ones."""
    rng = np.random.default_rng(seed)
    matches = np.unique(ds.match_ids)
    rng.shuffle(matches)
    n_val = max(1, int(len(matches) * val_fraction))
    val_matches = set(matches[:n_val].tolist())
    val_mask = np.isin(ds.match_ids, list(val_matches))
    def subset(mask: np.ndarray) -> Dataset:
        return Dataset(ds.features[mask], ds.labels[mask], ds.match_ids[mask])
    return subset(~val_mask), subset(val_mask)
