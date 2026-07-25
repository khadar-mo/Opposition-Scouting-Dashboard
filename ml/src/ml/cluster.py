"""Cluster possession sequences into recurring build-up patterns.

One global k-means model over all qualifying sequences (so cluster labels
mean the same thing for every team), then per-team usage shares. k-means on
standardised engineered features is deliberately simple: the clusters must
be explainable to a coach, not just separable. Run: python -m ml.cluster"""

import json
from collections import Counter
from typing import Any

import numpy as np
import psycopg
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ml.data import DATABASE_URL

K = 8
MIN_ACTIONS = 4
QUALIFYING_PATTERNS = ("Regular Play", "From Goal Kick", "From Counter", "From Throw In")

LANE_NAMES = ["the left wing", "the left half-space", "central areas",
              "the right half-space", "the right wing"]
NUMERIC_FEATURES = ["start_x", "start_y", "progression", "directness", "tempo",
                    "width_sd", "duration_s", "n_actions"]


def load_sequences(conn: psycopg.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.sequence_id, m.competition_id, m.season_id, s.team_id, s.features,
               s.ended_in_shot, coalesce(s.xg,0) AS xg, s.n_events
        FROM sequences s JOIN matches m USING (match_id)
        WHERE s.play_pattern = ANY(%s)
          AND (s.features->>'entered_final_third')::int = 1
          AND (s.features->>'n_actions')::int >= %s
        """,
        (list(QUALIFYING_PATTERNS), MIN_ACTIONS),
    ).fetchall()
    out = []
    for sid, comp_id, season_id, team_id, feats, shot, xg, n_events in rows:
        f = feats if isinstance(feats, dict) else json.loads(feats)
        f.update(sequence_id=sid, competition_id=comp_id, season_id=season_id,
                 team_id=team_id, ended_in_shot=shot, xg=xg, n_events=n_events)
        out.append(f)
    return out


def feature_matrix(seqs: list[dict[str, Any]]) -> np.ndarray:
    numeric = np.array([[s[k] for k in NUMERIC_FEATURES] for s in seqs])
    scaled = StandardScaler().fit_transform(numeric)
    lanes = np.array([s["entry_lane"] for s in seqs])
    onehot = np.zeros((len(seqs), 5))
    valid = lanes >= 0
    onehot[np.arange(len(seqs))[valid], lanes[valid]] = 1.0
    # Entry lane is the pattern's identity for an analyst; weight it up so
    # clusters split on where the final third is entered, not only on tempo.
    return np.hstack([scaled, onehot * 2.0])


def describe_cluster(members: list[dict[str, Any]]) -> tuple[str, str]:
    lanes = [s["entry_lane"] for s in members if s["entry_lane"] >= 0]
    lane_mode, lane_n = Counter(lanes).most_common(1)[0] if lanes else (2, 0)
    lane_share = lane_n / len(lanes) if lanes else 0.0
    start_x = float(np.mean([s["start_x"] for s in members]))
    directness = float(np.mean([s["directness"] for s in members]))
    duration = float(np.mean([s["duration_s"] for s in members]))
    n_actions = float(np.mean([s["n_actions"] for s in members]))
    shot_rate = float(np.mean([s["ended_in_shot"] for s in members]))

    origin = ("deep build-up" if start_x < 40
              else "midfield starts" if start_x < 70 else "high regains")
    style = ("direct" if directness >= 0.55
             else "patient" if directness <= 0.3 else "mixed-tempo")
    lane_name = LANE_NAMES[lane_mode]

    label = f"{origin.capitalize()}, {style}, entering via {lane_name}"
    description = (
        f"{origin.capitalize()} possessions ({style} progression, on average "
        f"{n_actions:.0f} on-ball actions over {duration:.0f}s) that reach the "
        f"final third most often through {lane_name} "
        f"({lane_share:.0%} of the cluster's entries). "
        f"{shot_rate:.0%} of these sequences end in a shot."
    )
    return label, description


def run() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        seqs = load_sequences(conn)
        print(f"{len(seqs)} qualifying sequences")
        matrix = feature_matrix(seqs)

        scores = {}
        for k in range(6, 11):
            km = KMeans(n_clusters=k, n_init=10, random_state=7).fit(matrix)
            scores[k] = silhouette_score(matrix, km.labels_, sample_size=4000,
                                         random_state=7)
        print("silhouette by k:", {k: round(v, 3) for k, v in scores.items()})

        km = KMeans(n_clusters=K, n_init=10, random_state=7).fit(matrix)
        labels = km.labels_

        conn.execute("DELETE FROM team_patterns")
        conn.execute("DELETE FROM pattern_clusters")
        conn.execute("UPDATE sequences SET cluster_id = NULL")

        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE sequences SET cluster_id = %s WHERE sequence_id = %s",
                [(int(c), s["sequence_id"]) for s, c in zip(seqs, labels, strict=True)],
            )
        for cid in range(K):
            members = [s for s, c in zip(seqs, labels, strict=True) if c == cid]
            label, description = describe_cluster(members)
            conn.execute(
                "INSERT INTO pattern_clusters VALUES (%s, %s, %s, %s)",
                (cid, label, description, len(members)),
            )
            print(f"cluster {cid} ({len(members)}): {label}")

        # Per-team-per-tournament shares + representative sequences
        # (shots first, then xG). Clusters themselves stay global so a
        # pattern label means the same thing in either competition.
        team_keys = {(s["competition_id"], s["season_id"], s["team_id"]) for s in seqs}
        for comp_id, season_id, team_id in team_keys:
            own = [
                (s, c)
                for s, c in zip(seqs, labels, strict=True)
                if (s["competition_id"], s["season_id"], s["team_id"])
                == (comp_id, season_id, team_id)
            ]
            n_team = len(own)
            for cid in range(K):
                members = [s for s, c in own if c == cid]
                if not members:
                    continue
                members.sort(
                    key=lambda s: (-int(s["ended_in_shot"]), -s["xg"], -s["n_events"])
                )
                reps = [int(s["sequence_id"]) for s in members[:3]]
                conn.execute(
                    "INSERT INTO team_patterns VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (comp_id, season_id, team_id, cid,
                     len(members), len(members) / n_team, reps),
                )
        conn.commit()
    print("clusters written")


if __name__ == "__main__":
    run()
