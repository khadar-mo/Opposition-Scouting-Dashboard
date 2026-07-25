"""Unit tests for derived-metric feature logic (no database required)."""

import polars as pl
from pipeline.derive import LANES, _corner_zone, _sequence_features, lane_of


def test_lanes_cover_pitch_width() -> None:
    assert lane_of(0) == 0 and LANES[lane_of(0)] == "wide_left"
    assert LANES[lane_of(20)] == "left_halfspace"
    assert LANES[lane_of(40)] == "central"
    assert LANES[lane_of(55)] == "right_halfspace"
    assert LANES[lane_of(79.9)] == "wide_right"
    assert lane_of(80) == 4  # boundary clamps into the last lane


def test_corner_zones() -> None:
    assert _corner_zone(118, 2, 0) == "short"
    assert _corner_zone(114, 35, 0) == "near_post"
    assert _corner_zone(114, 40, 0) == "central"
    assert _corner_zone(112, 50, 0) == "far_post"
    assert _corner_zone(104, 40, 0) == "edge_of_box"
    assert _corner_zone(90, 40, 0) == "out_of_box"


def _seq_frame(rows: list[tuple[str, float, float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "type": [r[0] for r in rows],
            "x": [r[1] for r in rows],
            "y": [r[2] for r in rows],
            "timestamp_s": [r[3] for r in rows],
        }
    )


def test_sequence_features_progression_and_entry_lane() -> None:
    seq = _seq_frame(
        [
            ("Pass", 30.0, 40.0, 0.0),
            ("Carry", 55.0, 30.0, 4.0),
            ("Pass", 85.0, 20.0, 8.0),  # crosses x=80 in the left half-space
            ("Shot", 105.0, 38.0, 10.0),
        ]
    )
    feats = _sequence_features(seq)
    assert feats is not None
    assert feats["progression"] == 75.0
    assert feats["entered_final_third"] == 1
    assert LANES[feats["entry_lane"]] == "left_halfspace"
    assert feats["n_actions"] == 4
    assert 0 < feats["directness"] <= 1


def test_sequence_features_rejects_tiny_possessions() -> None:
    assert _sequence_features(_seq_frame([("Pass", 30.0, 40.0, 0.0)])) is None
