"""Unit tests for the pure transformation logic (no database required)."""

from pipeline.ingest import _extract_event, _timestamp_to_seconds

SAMPLE_PASS = {
    "id": "f651a6c4-55e3-4e0f-a178-59414ba83d6a",
    "index": 5,
    "period": 1,
    "timestamp": "00:01:30.500",
    "minute": 1,
    "second": 30,
    "type": {"id": 30, "name": "Pass"},
    "possession": 2,
    "possession_team": {"id": 771, "name": "France"},
    "play_pattern": {"id": 9, "name": "From Kick Off"},
    "team": {"id": 771, "name": "France"},
    "player": {"id": 5487, "name": "Antoine Griezmann"},
    "position": {"id": 19, "name": "Center Attacking Midfield"},
    "location": [61.0, 40.1],
    "duration": 0.98,
    "pass": {
        "recipient": {"id": 10481, "name": "A. Tchouameni"},
        "length": 13.4,
        "end_location": [48.0, 43.2],
        "height": {"id": 1, "name": "Ground Pass"},
    },
}


def test_timestamp_to_seconds() -> None:
    assert _timestamp_to_seconds("00:00:00.578") == 0.578
    assert _timestamp_to_seconds("00:45:30.000") == 2730.0
    assert _timestamp_to_seconds("01:00:01.250") == 3601.25


def test_extract_pass_event() -> None:
    row = _extract_event(SAMPLE_PASS, match_id=123)
    assert row["event_id"] == SAMPLE_PASS["id"]
    assert row["match_id"] == 123
    assert row["type"] == "Pass"
    assert (row["x"], row["y"]) == (61.0, 40.1)
    assert (row["end_x"], row["end_y"]) == (48.0, 43.2)
    assert row["recipient_id"] == 10481
    assert row["outcome"] is None  # completed pass has no outcome
    assert row["under_pressure"] is False
    assert '"recipient"' in row["attrs"]


def test_extract_incomplete_pass_outcome() -> None:
    incomplete = {**SAMPLE_PASS["pass"], "outcome": {"id": 9, "name": "Incomplete"}}
    ev = {**SAMPLE_PASS, "pass": incomplete}
    assert _extract_event(ev, 123)["outcome"] == "Incomplete"


def test_extract_event_without_location() -> None:
    ev = {k: v for k, v in SAMPLE_PASS.items() if k not in ("location", "pass", "player")}
    ev["type"] = {"id": 35, "name": "Starting XI"}
    row = _extract_event(ev, 123)
    assert row["x"] is None
    assert row["player_id"] is None
    assert row["attrs"] is None
