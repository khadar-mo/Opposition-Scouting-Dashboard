import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def _team_ids(client: TestClient) -> dict[str, int]:
    return {t["name"]: t["team_id"] for t in client.get("/api/teams").json()}


def test_teams_lists_all_world_cup_teams(client: TestClient) -> None:
    teams = client.get("/api/teams").json()
    assert len(teams) == 32
    names = {t["name"] for t in teams}
    assert {"Argentina", "France", "Morocco"} <= names
    finalists = [t for t in teams if t["name"] in ("Argentina", "France")]
    assert all(t["n_matches"] == 7 for t in finalists)


def test_profile(client: TestClient) -> None:
    body = client.get(f"/api/teams/{_team_ids(client)['Argentina']}/profile").json()
    assert body["team"]["name"] == "Argentina"
    assert body["record"]["played"] == 7
    assert body["threat"]["sequences"] > 300
    assert body["threat"]["avg_directness"] is not None
    assert len(body["matches"]) == 7


def test_profile_unknown_team_404(client: TestClient) -> None:
    assert client.get("/api/teams/999999/profile").status_code == 404


def test_pass_network_shape_and_phase_validation(client: TestClient) -> None:
    tid = _team_ids(client)["France"]
    body = client.get(
        f"/api/teams/{tid}/pass-network", params={"phase": "open_play"}
    ).json()
    assert 0 < len(body["nodes"]) <= 11
    node_ids = {n["player_id"] for n in body["nodes"]}
    assert all(
        e["passer_id"] in node_ids and e["receiver_id"] in node_ids
        for e in body["edges"]
    )
    bad = client.get(f"/api/teams/{tid}/pass-network", params={"phase": "nope"})
    assert bad.status_code == 422


def test_set_pieces(client: TestClient) -> None:
    body = client.get(f"/api/teams/{_team_ids(client)['England']}/set-pieces").json()
    assert body["n_corners"] > 10
    zones = {z["delivery_zone"] for z in body["zones"]}
    assert zones <= {"short", "near_post", "central", "far_post", "edge_of_box", "out_of_box"}
