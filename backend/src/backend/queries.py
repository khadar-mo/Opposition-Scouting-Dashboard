"""All SQL lives here. Every query reads precomputed tables scoped to one
competition/season; the only per-request joins are cheap indexed lookups
(e.g. the events of one representative possession for pattern animation)."""

from typing import Any

from backend.db import fetch_all, fetch_one

MIN_WATCHLIST_MINUTES = 180.0


def list_competitions() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT c.competition_id, c.season_id, c.name, c.season_name,
               count(m.match_id) AS n_matches
        FROM competitions c
        JOIN matches m USING (competition_id, season_id)
        GROUP BY c.competition_id, c.season_id, c.name, c.season_name
        ORDER BY c.season_name DESC
        """
    )


def list_teams(competition_id: int, season_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT t.team_id, t.name, count(m.match_id) AS n_matches
        FROM teams t
        JOIN matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
        WHERE m.competition_id = %s AND m.season_id = %s
        GROUP BY t.team_id, t.name
        ORDER BY t.name
        """,
        (competition_id, season_id),
    )


def team_profile(
    team_id: int, competition_id: int, season_id: int
) -> dict[str, Any] | None:
    team = fetch_one("SELECT team_id, name FROM teams WHERE team_id = %s", (team_id,))
    if team is None:
        return None
    scope = {"id": team_id, "comp": competition_id, "season": season_id}
    record = fetch_one(
        """
        SELECT count(*) AS played,
               sum(CASE WHEN (m.home_team_id = %(id)s AND m.home_score > m.away_score)
                          OR (m.away_team_id = %(id)s AND m.away_score > m.home_score)
                        THEN 1 ELSE 0 END) AS won,
               sum(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) AS drawn,
               sum(CASE WHEN m.home_team_id = %(id)s THEN m.home_score ELSE m.away_score END)
                   AS goals_for,
               sum(CASE WHEN m.home_team_id = %(id)s THEN m.away_score ELSE m.home_score END)
                   AS goals_against
        FROM matches m
        WHERE (m.home_team_id = %(id)s OR m.away_team_id = %(id)s)
          AND m.competition_id = %(comp)s AND m.season_id = %(season)s
        """,
        scope,  # type: ignore[arg-type]
    )
    if record is None or not record["played"]:
        return None
    threat = fetch_one(
        """
        SELECT coalesce(sum(s.xg), 0)::float AS total_xg,
               count(*) FILTER (WHERE s.ended_in_shot) AS shot_sequences,
               count(*) AS sequences,
               avg(s.duration_s)::float AS avg_sequence_duration,
               avg((s.features->>'directness')::float)::float AS avg_directness
        FROM sequences s JOIN matches m USING (match_id)
        WHERE s.team_id = %(id)s
          AND m.competition_id = %(comp)s AND m.season_id = %(season)s
        """,
        scope,  # type: ignore[arg-type]
    )
    matches = fetch_all(
        """
        SELECT m.match_id, m.match_date, m.stage, m.home_score, m.away_score,
               ht.name AS home_team, at.name AS away_team
        FROM matches m
        JOIN teams ht ON ht.team_id = m.home_team_id
        JOIN teams at ON at.team_id = m.away_team_id
        WHERE (m.home_team_id = %(id)s OR m.away_team_id = %(id)s)
          AND m.competition_id = %(comp)s AND m.season_id = %(season)s
        ORDER BY m.match_date
        """,
        scope,  # type: ignore[arg-type]
    )
    return {"team": team, "record": record, "threat": threat, "matches": matches}


def threat_map(team_id: int, competition_id: int, season_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT zone_x, zone_y, xt::float, n_actions FROM zone_threat "
        "WHERE team_id = %s AND competition_id = %s AND season_id = %s "
        "ORDER BY zone_x, zone_y",
        (team_id, competition_id, season_id),
    )


def pass_network(
    team_id: int, phase: str, competition_id: int, season_id: int
) -> dict[str, Any]:
    # Show the 11 players most involved in that phase; a full tournament
    # squad on one pitch is unreadable.
    nodes = fetch_all(
        """
        SELECT pn.player_id, coalesce(p.nickname, p.name) AS name, p.jersey_number,
               p.position, pn.avg_x, pn.avg_y, pn.n_touches
        FROM pass_nodes pn JOIN players p USING (player_id)
        WHERE pn.team_id = %s AND pn.phase = %s
          AND pn.competition_id = %s AND pn.season_id = %s
        ORDER BY pn.n_touches DESC LIMIT 11
        """,
        (team_id, phase, competition_id, season_id),
    )
    ids = [n["player_id"] for n in nodes]
    edges = fetch_all(
        """
        SELECT passer_id, receiver_id, n_passes
        FROM pass_edges
        WHERE team_id = %s AND phase = %s
          AND competition_id = %s AND season_id = %s
          AND passer_id = ANY(%s) AND receiver_id = ANY(%s) AND n_passes >= 2
        ORDER BY n_passes DESC
        """,
        (team_id, phase, competition_id, season_id, ids, ids),
    )
    total = fetch_one(
        "SELECT coalesce(sum(n_passes), 0) AS n FROM pass_edges "
        "WHERE team_id = %s AND phase = %s AND competition_id = %s AND season_id = %s",
        (team_id, phase, competition_id, season_id),
    )
    return {"phase": phase, "nodes": nodes, "edges": edges,
            "total_passes": (total or {}).get("n", 0)}


def _sequence_steps(sequence_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT e.type, e.x, e.y, e.end_x, e.end_y, e.minute, e.second,
               coalesce(p.nickname, p.name) AS player
        FROM sequences s
        JOIN events e ON e.match_id = s.match_id AND e.possession = s.possession
                      AND e.team_id = s.team_id
        LEFT JOIN players p ON p.player_id = e.player_id
        WHERE s.sequence_id = %s
          AND e.type IN ('Pass', 'Carry', 'Shot', 'Dribble')
          AND e.x IS NOT NULL
        ORDER BY e.idx
        """,
        (sequence_id,),
    )


def patterns(team_id: int, competition_id: int, season_id: int) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT tp.cluster_id, pc.label, pc.description, tp.n_sequences, tp.pct,
               tp.representative_sequence_ids
        FROM team_patterns tp JOIN pattern_clusters pc USING (cluster_id)
        WHERE tp.team_id = %s AND tp.competition_id = %s AND tp.season_id = %s
        ORDER BY tp.pct DESC
        """,
        (team_id, competition_id, season_id),
    )
    for row in rows:
        reps = []
        for sid in row.pop("representative_sequence_ids")[:3]:
            meta = fetch_one(
                """
                SELECT s.sequence_id, s.match_id, s.xg, s.ended_in_shot,
                       ht.name AS home_team, at.name AS away_team, m.stage
                FROM sequences s
                JOIN matches m USING (match_id)
                JOIN teams ht ON ht.team_id = m.home_team_id
                JOIN teams at ON at.team_id = m.away_team_id
                WHERE s.sequence_id = %s
                """,
                (sid,),
            )
            if meta:
                meta["steps"] = _sequence_steps(sid)
                reps.append(meta)
        row["representatives"] = reps
    return rows


def set_pieces(team_id: int, competition_id: int, season_id: int) -> dict[str, Any]:
    scope = (team_id, competition_id, season_id)
    corners = fetch_all(
        """
        SELECT sp.side, sp.delivery_x, sp.delivery_y, sp.delivery_zone, sp.swing,
               sp.first_contact_x, sp.first_contact_y, sp.led_to_shot,
               sp.first_contact_team_id = sp.team_id AS won_first_contact,
               coalesce(p.nickname, p.name) AS first_contact_player
        FROM set_pieces sp
        JOIN matches m USING (match_id)
        LEFT JOIN players p ON p.player_id = sp.first_contact_player_id
        WHERE sp.team_id = %s AND sp.kind = 'corner'
          AND m.competition_id = %s AND m.season_id = %s
        """,
        scope,
    )
    zones = fetch_all(
        """
        SELECT sp.delivery_zone, count(*) AS n,
               count(*) FILTER (WHERE sp.led_to_shot) AS shots
        FROM set_pieces sp JOIN matches m USING (match_id)
        WHERE sp.team_id = %s AND sp.kind = 'corner'
          AND m.competition_id = %s AND m.season_id = %s
        GROUP BY sp.delivery_zone ORDER BY n DESC
        """,
        scope,
    )
    return {"corners": corners, "zones": zones, "n_corners": len(corners)}


def watchlist(team_id: int, competition_id: int, season_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT pt.player_id, coalesce(p.nickname, p.name) AS name, p.position,
               p.jersey_number, pt.minutes, pt.n_actions, pt.xt_total::float,
               pt.xt_per_90::float, pt.note
        FROM player_threat pt JOIN players p USING (player_id)
        WHERE pt.team_id = %s AND pt.competition_id = %s AND pt.season_id = %s
          AND pt.minutes >= %s
        ORDER BY pt.xt_per_90 DESC
        LIMIT 5
        """,
        (team_id, competition_id, season_id, MIN_WATCHLIST_MINUTES),
    )


def report(team_id: int, competition_id: int, season_id: int) -> dict[str, Any] | None:
    profile = team_profile(team_id, competition_id, season_id)
    if profile is None:
        return None
    zones = threat_map(team_id, competition_id, season_id)
    top_zones = sorted(zones, key=lambda z: -z["xt"])[:3]
    return {
        "profile": profile,
        "top_zones": top_zones,
        "patterns": [
            {k: p[k] for k in ("label", "description", "n_sequences", "pct")}
            for p in patterns(team_id, competition_id, season_id)[:3]
        ],
        "set_pieces": set_pieces(team_id, competition_id, season_id)["zones"],
        "watchlist": watchlist(team_id, competition_id, season_id)[:3],
    }
