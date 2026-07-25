import numpy as np
import polars as pl
from ml.data import Dataset, build_dataset, featurize, split_by_match


def test_featurize_ranges_and_geometry() -> None:
    x = np.array([0.0, 60.0, 120.0, 108.0])
    y = np.array([0.0, 40.0, 40.0, 40.0])
    f = featurize(x, y)
    assert f.shape == (4, 4)
    assert f.dtype == np.float32
    assert np.all(f >= 0) and np.all(f <= 1.001)
    # distance to goal shrinks as x approaches 120 down the middle
    assert f[1, 2] > f[3, 2] > f[2, 2]


def _actions(match_id: int, xgs: list[float]) -> pl.DataFrame:
    n = len(xgs)
    return pl.DataFrame(
        {
            "match_id": [match_id] * n,
            "possession": [1] * n,
            "team_id": [10] * n,
            "idx": list(range(n)),
            "type": ["Pass"] * n,
            "x": [50.0 + i for i in range(n)],
            "y": [40.0] * n,
            "end_x": [55.0 + i for i in range(n)],
            "end_y": [40.0] * n,
            "xg": xgs,
            "outcome": [None] * n,
        }
    )


def test_labels_look_ahead_k_actions() -> None:
    # xG arrives on the 7th action; only actions within 5 steps of it see it.
    ds = build_dataset(_actions(1, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4]), k=5)
    assert ds.labels.tolist() == [0.0, 0.0] + [np.float32(0.4)] * 5


def test_labels_capped_at_one() -> None:
    ds = build_dataset(_actions(1, [0.8, 0.9]), k=5)
    assert ds.labels.max() == 1.0


def test_split_by_match_has_no_leakage() -> None:
    rng = np.random.default_rng(0)
    n = 1000
    ds = Dataset(
        features=rng.random((n, 4), dtype=np.float32),
        labels=rng.random(n).astype(np.float32),
        match_ids=rng.integers(1, 21, size=n),
    )
    train, val = split_by_match(ds, val_fraction=0.25)
    assert len(train.labels) + len(val.labels) == n
    assert set(train.match_ids) & set(val.match_ids) == set()
    assert len(set(val.match_ids)) >= 4
