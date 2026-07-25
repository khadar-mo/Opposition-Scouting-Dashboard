-- Opposition Scouting Dashboard: normalised StatsBomb data + precomputed metrics.
-- Derived tables are populated at ingestion time so the API never computes on demand.

CREATE TABLE IF NOT EXISTS competitions (
    competition_id  INT NOT NULL,
    season_id       INT NOT NULL,
    name            TEXT NOT NULL,
    season_name     TEXT NOT NULL,
    PRIMARY KEY (competition_id, season_id)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id  INT PRIMARY KEY,
    name     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    player_id      INT PRIMARY KEY,
    name           TEXT NOT NULL,
    nickname       TEXT,
    team_id        INT NOT NULL REFERENCES teams(team_id),
    jersey_number  INT,
    position       TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    match_id       INT PRIMARY KEY,
    competition_id INT NOT NULL,
    season_id      INT NOT NULL,
    match_date     DATE NOT NULL,
    stage          TEXT NOT NULL,
    home_team_id   INT NOT NULL REFERENCES teams(team_id),
    away_team_id   INT NOT NULL REFERENCES teams(team_id),
    home_score     INT NOT NULL,
    away_score     INT NOT NULL
);

-- One row per event; frequent analytic fields are first-class columns,
-- the type-specific payload (pass{}, shot{}, carry{}, ...) is kept in attrs.
CREATE TABLE IF NOT EXISTS events (
    event_id           UUID PRIMARY KEY,
    match_id           INT NOT NULL REFERENCES matches(match_id),
    idx                INT NOT NULL,
    period             INT NOT NULL,
    timestamp_s        DOUBLE PRECISION NOT NULL,
    minute             INT NOT NULL,
    second             INT NOT NULL,
    possession         INT NOT NULL,
    possession_team_id INT NOT NULL,
    play_pattern       TEXT NOT NULL,
    team_id            INT NOT NULL,
    player_id          INT,
    position           TEXT,
    type               TEXT NOT NULL,
    x                  DOUBLE PRECISION,
    y                  DOUBLE PRECISION,
    end_x              DOUBLE PRECISION,
    end_y              DOUBLE PRECISION,
    outcome            TEXT,
    recipient_id       INT,
    xg                 DOUBLE PRECISION,
    under_pressure     BOOLEAN NOT NULL DEFAULT FALSE,
    duration           DOUBLE PRECISION,
    attrs              JSONB
);
CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id, idx);
CREATE INDEX IF NOT EXISTS idx_events_team_type ON events(team_id, type);
CREATE INDEX IF NOT EXISTS idx_events_possession ON events(match_id, possession);

-- 360 freeze frames: player positions at the moment of selected events.
CREATE TABLE IF NOT EXISTS freeze_frames (
    event_id  UUID NOT NULL REFERENCES events(event_id),
    teammate  BOOLEAN NOT NULL,
    actor     BOOLEAN NOT NULL,
    keeper    BOOLEAN NOT NULL,
    x         DOUBLE PRECISION NOT NULL,
    y         DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_freeze_frames_event ON freeze_frames(event_id);

-- ---------- Derived tables (populated by the derive step) ----------

-- Minutes played per player per match (from lineup position stints).
CREATE TABLE IF NOT EXISTS player_minutes (
    match_id   INT NOT NULL REFERENCES matches(match_id),
    player_id  INT NOT NULL REFERENCES players(player_id),
    minutes    DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (match_id, player_id)
);

-- One row per possession sequence of the team in possession.
CREATE TABLE IF NOT EXISTS sequences (
    sequence_id    BIGSERIAL PRIMARY KEY,
    match_id       INT NOT NULL REFERENCES matches(match_id),
    team_id        INT NOT NULL REFERENCES teams(team_id),
    possession     INT NOT NULL,
    start_x        DOUBLE PRECISION,
    start_y        DOUBLE PRECISION,
    end_x          DOUBLE PRECISION,
    end_y          DOUBLE PRECISION,
    n_events       INT NOT NULL,
    duration_s     DOUBLE PRECISION,
    ended_in_shot  BOOLEAN NOT NULL DEFAULT FALSE,
    xg             DOUBLE PRECISION,
    play_pattern   TEXT,
    features       JSONB,
    cluster_id     INT,
    UNIQUE (match_id, possession, team_id)
);
CREATE INDEX IF NOT EXISTS idx_sequences_team ON sequences(team_id, cluster_id);

-- Per-team aggregates are competition-scoped: the same national team appears
-- in multiple tournaments and its profiles must never mix.

-- xT generated per pitch zone per team (12x8 grid on the 120x80 pitch).
CREATE TABLE IF NOT EXISTS zone_threat (
    competition_id INT NOT NULL,
    season_id      INT NOT NULL,
    team_id    INT NOT NULL REFERENCES teams(team_id),
    zone_x     INT NOT NULL,
    zone_y     INT NOT NULL,
    xt         DOUBLE PRECISION NOT NULL,
    n_actions  INT NOT NULL,
    xt_pressured DOUBLE PRECISION NOT NULL DEFAULT 0,
    n_pressured  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (competition_id, season_id, team_id, zone_x, zone_y)
);

-- Aggregated pass-network edges and nodes per team and phase of play.
CREATE TABLE IF NOT EXISTS pass_edges (
    competition_id INT NOT NULL,
    season_id      INT NOT NULL,
    team_id      INT NOT NULL REFERENCES teams(team_id),
    phase        TEXT NOT NULL,
    passer_id    INT NOT NULL,
    receiver_id  INT NOT NULL,
    n_passes     INT NOT NULL,
    PRIMARY KEY (competition_id, season_id, team_id, phase, passer_id, receiver_id)
);

CREATE TABLE IF NOT EXISTS pass_nodes (
    competition_id INT NOT NULL,
    season_id      INT NOT NULL,
    team_id    INT NOT NULL REFERENCES teams(team_id),
    phase      TEXT NOT NULL,
    player_id  INT NOT NULL REFERENCES players(player_id),
    avg_x      DOUBLE PRECISION NOT NULL,
    avg_y      DOUBLE PRECISION NOT NULL,
    n_touches  INT NOT NULL,
    PRIMARY KEY (competition_id, season_id, team_id, phase, player_id)
);

-- Per-player threat contribution (filled after the xT model runs).
CREATE TABLE IF NOT EXISTS player_threat (
    competition_id INT NOT NULL,
    season_id      INT NOT NULL,
    team_id     INT NOT NULL REFERENCES teams(team_id),
    player_id   INT NOT NULL REFERENCES players(player_id),
    minutes     DOUBLE PRECISION NOT NULL,
    n_actions   INT NOT NULL,
    xt_total    DOUBLE PRECISION NOT NULL,
    xt_per_90   DOUBLE PRECISION NOT NULL,
    note        TEXT,
    PRIMARY KEY (competition_id, season_id, team_id, player_id)
);

-- Set pieces (corners first): delivery location + first contact from 360 data.
CREATE TABLE IF NOT EXISTS set_pieces (
    event_id               UUID PRIMARY KEY REFERENCES events(event_id),
    match_id               INT NOT NULL REFERENCES matches(match_id),
    team_id                INT NOT NULL REFERENCES teams(team_id),
    kind                   TEXT NOT NULL,
    side                   TEXT,
    delivery_x             DOUBLE PRECISION,
    delivery_y             DOUBLE PRECISION,
    delivery_zone          TEXT,
    swing                  TEXT,
    first_contact_team_id  INT,
    first_contact_player_id INT,
    first_contact_x        DOUBLE PRECISION,
    first_contact_y        DOUBLE PRECISION,
    led_to_shot            BOOLEAN NOT NULL DEFAULT FALSE
);

-- Build-up pattern clusters (global model, per-team usage shares).
CREATE TABLE IF NOT EXISTS pattern_clusters (
    cluster_id   INT PRIMARY KEY,
    label        TEXT NOT NULL,
    description  TEXT NOT NULL,
    n_sequences  INT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_patterns (
    competition_id              INT NOT NULL,
    season_id                   INT NOT NULL,
    team_id                     INT NOT NULL REFERENCES teams(team_id),
    cluster_id                  INT NOT NULL REFERENCES pattern_clusters(cluster_id),
    n_sequences                 INT NOT NULL,
    pct                         DOUBLE PRECISION NOT NULL,
    representative_sequence_ids BIGINT[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (competition_id, season_id, team_id, cluster_id)
);
