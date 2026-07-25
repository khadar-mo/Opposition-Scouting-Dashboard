"""Does defensive context improve the threat model? A 360 ablation.

Two identical MLPs, identical match-level split, identical training budget,
on the SAME subset of actions (those covered by a 360 freeze-frame):

  A) position features only            (x, y, dist, angle)
  B) position + defender context       (+ nearest_def, n_ahead, n_cone)

Run: python -m ml.pressure_ablation
"""

import json

import numpy as np
import polars as pl
import psycopg
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ml.data import DATABASE_URL, Dataset, build_dataset, load_actions, split_by_match
from ml.pressure import pressure_features
from ml.xt_model import ARTIFACTS_DIR, XTNet

EPOCHS = 40
BATCH = 4096
LR = 1e-3
PATIENCE = 5


def _train_one(
    train_ds: Dataset, val_ds: Dataset, n_features: int, seed: int = 7
) -> float:
    torch.manual_seed(seed)
    model = XTNet(n_features=n_features)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.BCEWithLogitsLoss()
    loader = DataLoader(
        TensorDataset(
            torch.from_numpy(train_ds.features), torch.from_numpy(train_ds.labels)
        ),
        batch_size=BATCH,
        shuffle=True,
    )
    x_val = torch.from_numpy(val_ds.features)
    y_val = torch.from_numpy(val_ds.labels)
    best, stale = float("inf"), 0
    for _ in range(EPOCHS):
        model.train()
        for xb, yb in loader:
            opt.zero_grad()
            loss_fn(model(xb), yb).backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val = loss_fn(model(x_val), y_val).item()
        if val < best - 1e-5:
            best, stale = val, 0
        else:
            stale += 1
            if stale >= PATIENCE:
                break
    return best


def _with_pressure(ds: Dataset, press: dict[str, np.ndarray]) -> Dataset:
    assert ds.event_ids is not None
    extra = np.stack([press[c] for c in ("nearest_def", "n_ahead", "n_cone")], axis=1)
    return Dataset(
        np.hstack([ds.features, extra.astype(np.float32)]),
        ds.labels, ds.match_ids, ds.event_ids,
    )


def run() -> None:
    actions = load_actions()
    ds = build_dataset(actions)
    assert ds.event_ids is not None

    with psycopg.connect(DATABASE_URL) as conn:
        press = pressure_features(conn)
        # Sanity: the StatsBomb under_pressure flag should agree with 360 geometry.
        flag = conn.execute(
            "SELECT event_id::text, under_pressure FROM events "
            "WHERE type IN ('Pass','Carry','Shot','Dribble') AND x IS NOT NULL"
        ).fetchall()
    flag_df = pl.DataFrame(flag, schema=["event_id", "under_pressure"], orient="row")
    joined = press.join(flag_df, on="event_id", how="inner")
    med = joined.group_by("under_pressure").agg(pl.col("nearest_def").median())
    med_map = {bool(r[0]): float(r[1]) for r in med.iter_rows()}

    covered = {r["event_id"]: r for r in press.iter_rows(named=True)}
    all_event_ids = ds.event_ids
    mask = np.array([e in covered for e in all_event_ids])
    sub_event_ids: np.ndarray = all_event_ids[mask]
    sub = Dataset(ds.features[mask], ds.labels[mask], ds.match_ids[mask],
                  sub_event_ids)
    print(f"{mask.sum()} of {len(mask)} actions covered by 360 frames "
          f"({mask.mean():.0%})")

    # Normalised defender-context features aligned to the subset.
    ctx = {
        "nearest_def": np.array(
            [min(covered[e]["nearest_def"], 20.0) / 20.0 for e in sub_event_ids]
        ),
        "n_ahead": np.array([covered[e]["n_ahead"] / 11.0 for e in sub_event_ids]),
        "n_cone": np.array([min(covered[e]["n_cone"], 8) / 8.0 for e in sub_event_ids]),
    }

    train_a, val_a = split_by_match(sub)
    bce_pos = _train_one(train_a, val_a, n_features=4)

    sub_p = _with_pressure(sub, ctx)
    train_b, val_b = split_by_match(sub_p)
    bce_ctx = _train_one(train_b, val_b, n_features=7)

    base = float(np.mean(train_a.labels))
    eps = 1e-7
    p = np.clip(base, eps, 1 - eps)
    y = val_a.labels
    bce_base = float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p))))

    results = {
        "n_actions_covered": int(mask.sum()),
        "coverage": float(mask.mean()),
        "val_bce_baseline": bce_base,
        "val_bce_position_only": bce_pos,
        "val_bce_with_pressure": bce_ctx,
        "improvement_over_position_only": 1 - bce_ctx / bce_pos,
        "median_nearest_def_flagged": med_map.get(True),
        "median_nearest_def_unflagged": med_map.get(False),
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "pressure_ablation.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run()
