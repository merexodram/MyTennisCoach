-- MyTennisCoach database schema (DuckDB).
-- Design rule: everything the coach needs later is stored here as numbers,
-- so raw video can be deleted after a session has been reviewed.

CREATE TABLE IF NOT EXISTS sessions (
    session_id   INTEGER PRIMARY KEY,
    played_on    DATE NOT NULL,
    kind         VARCHAR NOT NULL,          -- 'match' | 'training' | 'reference' (pro footage)
    source       VARCHAR NOT NULL,          -- 'action_cam' | 'phone' | 'broadcast'
    player       VARCHAR,                   -- who is analysed
    opponent     VARCHAR,
    surface      VARCHAR,                   -- 'hard' | 'clay' | 'grass' | 'carpet'
    location     VARCHAR,
    camera_view  VARCHAR,                   -- 'behind_baseline' | 'side_on' | 'broadcast'
    fps          DOUBLE,
    width        INTEGER,
    height       INTEGER,
    duration_s   DOUBLE,
    video_file   VARCHAR,                   -- local path; NULL once the raw video is deleted
    pipeline_ver VARCHAR,                   -- git commit of this repo used for processing
    notes        VARCHAR
);

CREATE TABLE IF NOT EXISTS points (
    point_id     INTEGER PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES sessions(session_id),
    seq          INTEGER NOT NULL,          -- order within the session
    start_frame  INTEGER,
    end_frame    INTEGER,
    server       VARCHAR,                   -- 'me' | 'opponent'
    rally_length INTEGER,                   -- number of shots
    winner       VARCHAR,                   -- 'me' | 'opponent' | NULL if unknown
    end_reason   VARCHAR                    -- 'winner' | 'forced_error' | 'unforced_error' | 'ace' | 'double_fault'
);

CREATE TABLE IF NOT EXISTS shots (
    shot_id      INTEGER PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES sessions(session_id),
    point_id     INTEGER REFERENCES points(point_id),
    seq          INTEGER,                   -- order within the point
    frame        INTEGER NOT NULL,          -- contact frame
    t_s          DOUBLE,                    -- time of contact in the video
    hitter       VARCHAR,                   -- 'me' | 'opponent'
    stroke       VARCHAR,                   -- 'serve' | 'forehand' | 'backhand' | 'volley' | 'smash' | 'slice' | 'unknown'
    contact_x_m  DOUBLE,                    -- hitter position on court, metres, origin = court centre
    contact_y_m  DOUBLE,
    bounce_x_m   DOUBLE,                    -- where the ball landed
    bounce_y_m   DOUBLE,
    in_court     BOOLEAN,
    speed_kmh    DOUBLE,                    -- estimate from a single camera; treat as relative
    direction    VARCHAR,                   -- 'cross' | 'line' | 'middle'
    depth        VARCHAR,                   -- 'short' | 'mid' | 'deep'
    outcome      VARCHAR,                   -- 'in_play' | 'winner' | 'fault' | 'error_net' | 'error_long' | 'error_wide'
    confidence   DOUBLE                     -- 0..1, how sure the pipeline is about this row
);

CREATE TABLE IF NOT EXISTS pose_metrics (
    shot_id            INTEGER PRIMARY KEY REFERENCES shots(shot_id),
    contact_height_m   DOUBLE,
    contact_front_m    DOUBLE,              -- contact point ahead (+) or behind (-) the front hip
    knee_flex_deg      DOUBLE,              -- minimum knee angle during loading
    hip_shoulder_sep_deg DOUBLE,            -- separation at end of backswing
    elbow_angle_deg    DOUBLE,              -- at contact
    trunk_tilt_deg     DOUBLE,
    stance             VARCHAR,             -- 'open' | 'semi_open' | 'neutral' | 'closed'
    split_step         BOOLEAN,
    swing_duration_s   DOUBLE
);

-- Added with the technique layer (existing databases are upgraded in place).
ALTER TABLE pose_metrics ADD COLUMN IF NOT EXISTS contact_reach_m DOUBLE;      -- hitting hand sideways from the hips
ALTER TABLE pose_metrics ADD COLUMN IF NOT EXISTS shoulder_turn_deg DOUBLE;    -- estimate from apparent shoulder width
ALTER TABLE pose_metrics ADD COLUMN IF NOT EXISTS off_hand_on_racket BOOLEAN;  -- at contact
ALTER TABLE pose_metrics ADD COLUMN IF NOT EXISTS pose_frames INTEGER;         -- frames with a usable pose

-- Ball flight in 3D (flight.py) and movement, added with the metrics layer.
ALTER TABLE shots ADD COLUMN IF NOT EXISTS net_clearance_m DOUBLE;   -- height above the net tape
ALTER TABLE shots ADD COLUMN IF NOT EXISTS apex_m DOUBLE;            -- highest point of the flight
ALTER TABLE shots ADD COLUMN IF NOT EXISTS spin_rpm DOUBLE;          -- + topspin, - slice (experimental)
ALTER TABLE shots ADD COLUMN IF NOT EXISTS bounce_angle_deg DOUBLE;  -- steepness of the landing
ALTER TABLE shots ADD COLUMN IF NOT EXISTS hit_height_m DOUBLE;      -- ball height at contact (from the flight)
ALTER TABLE shots ADD COLUMN IF NOT EXISTS flight_fit_px DOUBLE;     -- fit error of the flight, pixels
ALTER TABLE points ADD COLUMN IF NOT EXISTS me_distance_m DOUBLE;    -- how far I ran in the rally
ALTER TABLE points ADD COLUMN IF NOT EXISTS me_behind_baseline_m DOUBLE; -- my average position behind my baseline
ALTER TABLE points ADD COLUMN IF NOT EXISTS seconds DOUBLE;

-- One row per session and metric (metrics.py). source: 'auto' measured from
-- the video, 'coach' told to the coach in the review chat.
CREATE TABLE IF NOT EXISTS session_metrics (
    session_id INTEGER NOT NULL,
    metric     VARCHAR NOT NULL,
    value      DOUBLE,
    n          INTEGER,                  -- how many strokes/points the value rests on
    source     VARCHAR NOT NULL,
    PRIMARY KEY (session_id, metric)
);

CREATE TABLE IF NOT EXISTS clips (
    clip_id      INTEGER PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES sessions(session_id),
    shot_id      INTEGER REFERENCES shots(shot_id),
    file         VARCHAR NOT NULL,          -- short clip kept after the raw video is deleted
    reason       VARCHAR NOT NULL,          -- 'error_example' | 'best_example' | 'monthly_reference' | 'coach_flag'
    keep_until   DATE                       -- NULL = keep indefinitely
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id    INTEGER PRIMARY KEY,
    session_id   INTEGER REFERENCES sessions(session_id),
    created_on   DATE NOT NULL,
    scope        VARCHAR NOT NULL,          -- 'session' | 'monthly'
    summary_md   VARCHAR,                   -- the written coaching review
    focus_points VARCHAR,                   -- 2-3 priorities, one per line
    drills       VARCHAR
);

-- Per-session, per-stroke summary used by the coach for trends.
CREATE OR REPLACE VIEW stroke_summary AS
SELECT s.session_id,
       se.played_on,
       s.hitter,
       s.stroke,
       count(*)                                              AS shots,
       avg(CASE WHEN s.in_court THEN 1.0 ELSE 0.0 END)       AS in_rate,
       avg(s.speed_kmh)                                      AS avg_speed_kmh,
       avg(CASE WHEN s.depth = 'deep' THEN 1.0 ELSE 0.0 END) AS deep_rate,
       avg(CASE WHEN s.outcome LIKE 'error%' THEN 1.0 ELSE 0.0 END) AS error_rate
FROM shots s
JOIN sessions se USING (session_id)
GROUP BY ALL;
