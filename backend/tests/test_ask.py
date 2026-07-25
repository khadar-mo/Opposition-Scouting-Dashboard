import pytest
from backend.ask import _zone_name, build_context, is_enabled
from fastapi.testclient import TestClient


def test_zone_names() -> None:
    assert _zone_name(11, 2) == "final third / left half-space"
    assert _zone_name(0, 0) == "own third / left wing"
    assert _zone_name(5, 7) == "middle third / right wing"


def test_disabled_without_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not is_enabled()
    resp = client.post("/api/teams/779/ask", json={"question": "How do they attack?"})
    assert resp.status_code == 503
    health = client.get("/api/health").json()
    assert health["ask_enabled"] is False


def test_question_validation(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-never-used")
    # Too-short question is rejected by schema before any model call happens.
    resp = client.post("/api/teams/779/ask", json={"question": "hi"})
    assert resp.status_code == 422


@pytest.mark.integration
def test_context_is_grounded_in_dashboard_data(client: TestClient) -> None:
    teams = {t["name"]: t["team_id"] for t in client.get("/api/teams").json()}
    ctx = build_context(teams["Argentina"], 43, 106)
    assert ctx is not None
    assert ctx["team"] == "Argentina"
    assert ctx["record"]["played"] == 7
    assert len(ctx["top_threat_zones"]) == 10
    zone = ctx["top_threat_zones"][0]
    assert 0 < zone["share_of_team_threat"] < 1
    assert zone["n_actions"] > 0
    assert ctx["player_watchlist"], "watchlist must be part of the grounding data"
    # Unknown team yields no context (endpoint 404s)
    assert build_context(999999, 43, 106) is None
