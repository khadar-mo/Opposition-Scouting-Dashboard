import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["ask_enabled"], bool)


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


EURO = {"competition_id": 55, "season_id": 282}


def test_competitions_endpoint(client: TestClient) -> None:
    comps = client.get('/api/competitions').json()
    keys = {(c['competition_id'], c['season_id']) for c in comps}
    assert {(43, 106), (55, 282)} <= keys
    wc = next(c for c in comps if c['season_id'] == 106)
    assert wc['n_matches'] == 64


def test_euro_2024_teams_scoped(client: TestClient) -> None:
    euro_teams = client.get('/api/teams', params=EURO).json()
    assert len(euro_teams) == 24
    names = {t['name'] for t in euro_teams}
    assert 'Spain' in names and 'Argentina' not in names
    finalists = [t for t in euro_teams if t['name'] in ('Spain', 'England')]
    assert all(t['n_matches'] == 7 for t in finalists)


def test_profiles_do_not_mix_competitions(client: TestClient) -> None:
    euro_teams = {t['name']: t['team_id'] for t in client.get('/api/teams', params=EURO).json()}
    spain = euro_teams['Spain']
    euro_profile = client.get(f'/api/teams/{spain}/profile', params=EURO).json()
    wc_profile = client.get(f'/api/teams/{spain}/profile').json()
    assert euro_profile['record']['played'] == 7   # Euro 2024 winners
    assert wc_profile['record']['played'] == 4     # WC 2022 last-16 exit
    assert euro_profile['threat']['sequences'] != wc_profile['threat']['sequences']


def test_team_absent_from_competition_404s(client: TestClient) -> None:
    argentina = _team_ids(client)['Argentina']
    assert client.get(f'/api/teams/{argentina}/profile', params=EURO).status_code == 404


def test_euro_watchlist_and_threat_map_populated(client: TestClient) -> None:
    euro_teams = {t['name']: t['team_id'] for t in client.get('/api/teams', params=EURO).json()}
    tid = euro_teams['Spain']
    zones = client.get(f'/api/teams/{tid}/threat-map', params=EURO).json()
    assert len(zones) > 50 and all(z['xt'] >= 0 for z in zones)
    watch = client.get(f'/api/teams/{tid}/watchlist', params=EURO).json()
    assert len(watch) == 5 and watch[0]['xt_per_90'] > 0
