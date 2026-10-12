# Metrics

Every session gets one value per metric below, stored in the table
`session_metrics` of `data\tennis.duckdb`. That is what makes any two sessions,
or a session and your all-time best, comparable: in `outputs\dashboard.html`,
in the Obsidian notes and in the coach's reviews.

The list follows what professional match statisticians log (serve, return,
rally length, winners and errors, net play), plus what a camera adds
(ball flight, position, movement, technique) and what only you know
(score, how it felt).

## Where a value comes from

| Source | Meaning |
|---|---|
| measured | counted from the video by the pipeline |
| measured, one-camera estimate (~) | computed from the video with a physical model; good for trends with the same camera position, not as an absolute number |
| told to the coach | asked in the review chat and stored from `coach_input.json`; a value told to the coach replaces the measured one (e.g. if the camera missed a double fault) |

Each value also records how many strokes or points it rests on. Below the
minimum sample it is shown in grey and left out of comparisons and records.

## How the harder ones are measured

- **First and second serve.** My serves in time order: a serve within 25 s of
  a first-serve fault is a second serve; a second serve that misses is a
  double fault. A serve must land in the diagonal service box.
- **Unforced and forced errors.** Statisticians judge this by eye. The rule
  here: an error is forced when the incoming ball was among the fastest
  quarter of the session, when it was a return of a serve that landed in, or
  when I had to hit from more than 1.2 m outside the singles line or 3.5 m
  behind the baseline. Correct it in the chat if it is wrong.
- **Errors** count only the shot that ended the point. An "out" mark in the
  middle of a rally that went on is a tracking mistake and is not counted.
- **Ball flight (speed, net clearance, highest point, spin, landing angle).**
  `src/mytenniscoach/flight.py`. The court calibration also gives the camera
  itself: focal length, height and angle. The flight between contact and
  bounce is then fitted with gravity, air drag and the Magnus force of spin
  to every ball position in the picture. Fits that miss the picture by more
  than a few pixels, cross below the net tape, or put the contact at an
  impossible height are dropped. Needs a camera **without fisheye**: set the
  action cam to its linear lens mode. Spin is experimental: it trades off
  against speed in the fit, so read it only as a trend.
- **Movement.** My position on court every 0.2 s during each rally (feet,
  through the court mapping), smoothed; jumps faster than 9 m/s are ignored.
- **Technique.** From the pose of my strokes (`technique.py`); one value per
  stroke type and session, plus the spread as a measure of how repeatable it is.

## Not measured (yet)

Score, break points and tie-breaks need the score of every point: tell them
to the coach. First-step reaction, split-step timing and contact point in
front of the body are not built yet. Ball speed off the racket from a single
camera is an estimate; a radar gun is the reference if you ever want to
calibrate it.

## The catalogue

### Serve

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Serves hit | `serves` | count | – | measured | 1 |  |
| 1st serve in | `first_serve_in_pct` | % | high | measured | 5 |  |
| 2nd serve in | `second_serve_in_pct` | % | high | measured | 3 |  |
| Double faults | `double_faults` | count | low | measured | 1 |  |
| Double faults per service point | `double_fault_pct` | % | low | measured | 5 |  |
| Unreturned serves (aces and serve winners) | `unreturned_serves` | count | high | measured | 1 |  |
| Points won on 1st serve | `first_serve_won_pct` | % | high | measured | 5 | only points whose end the camera saw |
| Points won on 2nd serve | `second_serve_won_pct` | % | high | measured | 3 |  |
| 1st serve speed, average | `first_serve_kmh` | km/h | high | measured, one-camera estimate | 3 |  |
| 1st serve speed, fastest | `first_serve_kmh_max` | km/h | high | measured, one-camera estimate | 3 |  |
| 2nd serve speed, average | `second_serve_kmh` | km/h | – | measured, one-camera estimate | 3 |  |
| Serves to the T | `serve_t_pct` | % | – | measured | 5 |  |
| Serves wide | `serve_wide_pct` | % | – | measured | 5 |  |
| Serves to the body | `serve_body_pct` | % | – | measured | 5 |  |
| Serve contact height | `serve_contact_m` | m | high | measured | 3 | from the pose |

### Return

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Returns hit | `returns` | count | – | measured | 1 |  |
| Returns in | `return_in_pct` | % | high | measured | 5 |  |
| Returns landing deep | `return_deep_pct` | % | high | measured | 5 |  |
| Return points won | `return_won_pct` | % | high | measured | 5 |  |

### Rally

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Points (rallies) seen | `points` | count | – | measured | 1 |  |
| Points won | `points_won_pct` | % | high | measured | 10 | points whose end the camera saw |
| Average rally length | `rally_avg` | shots | – | measured | 5 |  |
| Longest rally | `rally_max` | shots | high | measured | 1 |  |
| Rallies of 0-4 shots | `rally_short_pct` | % | – | measured | 10 |  |
| Rallies of 5-8 shots | `rally_mid_pct` | % | – | measured | 10 |  |
| Rallies of 9+ shots | `rally_long_pct` | % | – | measured | 10 |  |
| Points won in 0-4 shot rallies | `won_short_pct` | % | high | measured | 5 |  |
| Points won in 5+ shot rallies | `won_long_pct` | % | high | measured | 5 |  |

### Groundstrokes

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Forehands | `forehands` | count | – | measured | 1 |  |
| Backhands | `backhands` | count | – | measured | 1 |  |
| Forehand share of groundstrokes | `forehand_share_pct` | % | – | measured | 10 |  |
| Forehands in | `fh_in_pct` | % | high | measured | 10 |  |
| Backhands in | `bh_in_pct` | % | high | measured | 10 |  |
| Forehand speed, average | `fh_kmh` | km/h | high | measured, one-camera estimate | 5 |  |
| Backhand speed, average | `bh_kmh` | km/h | high | measured, one-camera estimate | 5 |  |
| Forehand speed, top 10 % | `fh_kmh_top` | km/h | high | measured, one-camera estimate | 10 |  |
| Backhand speed, top 10 % | `bh_kmh_top` | km/h | high | measured, one-camera estimate | 10 |  |
| Forehands landing deep (last 3 m) | `fh_deep_pct` | % | high | measured | 10 |  |
| Backhands landing deep (last 3 m) | `bh_deep_pct` | % | high | measured | 10 |  |
| My balls landing before the service line | `short_ball_pct` | % | low | measured | 10 |  |
| Forehands cross-court | `fh_cross_pct` | % | – | measured | 10 |  |
| Backhands cross-court | `bh_cross_pct` | % | – | measured | 10 |  |
| Average landing distance from the net | `avg_depth_m` | m | high | measured | 10 |  |

### Ball flight

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Forehand net clearance | `fh_net_clear_m` | m | – | measured, one-camera estimate | 5 | about 0.6-1.2 m is the safe window for rally balls |
| Backhand net clearance | `bh_net_clear_m` | m | – | measured, one-camera estimate | 5 |  |
| Forehand highest point | `fh_apex_m` | m | – | measured, one-camera estimate | 5 |  |
| Backhand highest point | `bh_apex_m` | m | – | measured, one-camera estimate | 5 |  |
| Forehand spin (+ topspin) | `fh_spin_rpm` | rpm | – | measured, one-camera estimate | 5 | experimental: trust the trend, not the number |
| Backhand spin (+ topspin, - slice) | `bh_spin_rpm` | rpm | – | measured, one-camera estimate | 5 | experimental |
| Forehand landing angle | `fh_bounce_deg` | deg | – | measured, one-camera estimate | 5 | steeper = more topspin and kick |
| Backhand landing angle | `bh_bounce_deg` | deg | – | measured, one-camera estimate | 5 |  |

### Errors

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Winners | `winners` | count | high | measured | 1 |  |
| Unforced errors | `unforced_errors` | count | low | measured | 1 | forced/unforced is judged by rule: fast incoming ball or stretched = forced |
| Forced errors | `forced_errors` | count | – | measured | 1 |  |
| Winners / unforced errors | `winner_ue_ratio` | ratio | high | measured | 5 |  |
| Unforced errors per 100 of my shots | `ue_per_100` | per 100 | low | measured | 30 |  |
| Errors into the net | `errors_net` | count | low | measured | 1 |  |
| Errors long | `errors_long` | count | low | measured | 1 |  |
| Errors wide | `errors_wide` | count | low | measured | 1 |  |
| Forehand errors | `fh_errors` | count | low | measured | 1 |  |
| Backhand errors | `bh_errors` | count | low | measured | 1 |  |
| My shots in a row before an error (consistency) | `shots_before_error` | shots | high | measured | 3 |  |

### Net

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Points where I came to the net | `net_points` | count | – | measured | 1 |  |
| Net points won | `net_won_pct` | % | high | measured | 3 |  |
| Volleys | `volleys` | count | – | measured | 1 |  |

### Movement

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Average contact distance behind my baseline | `contact_behind_m` | m | low | measured | 10 | smaller = taking the ball earlier |
| Groundstrokes taken inside the baseline | `inside_baseline_pct` | % | high | measured | 10 |  |
| Distance run per point | `distance_per_point_m` | m | – | measured | 5 |  |
| Distance run in rallies | `distance_total_m` | m | – | measured | 1 |  |
| Average position behind my baseline during rallies | `rest_position_m` | m | low | measured | 5 |  |

### Technique

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Forehand contact height | `fh_contact_height_m` | m | – | measured | 5 |  |
| Backhand contact height | `bh_contact_height_m` | m | – | measured | 5 |  |
| Forehand contact height, spread | `fh_contact_spread_m` | m | low | measured | 5 | smaller = more repeatable contact |
| Backhand contact height, spread | `bh_contact_spread_m` | m | low | measured | 5 |  |
| Forehand contact distance from the body | `fh_reach_m` | m | – | measured | 5 |  |
| Backhand contact distance from the body | `bh_reach_m` | m | – | measured | 5 |  |
| Forehand knee angle at loading | `fh_knee_deg` | deg | low | measured | 5 | smaller = deeper bend |
| Backhand knee angle at loading | `bh_knee_deg` | deg | low | measured | 5 |  |
| Forehands from an open or semi-open stance | `fh_open_stance_pct` | % | – | measured | 5 |  |
| Backhands from a closed or neutral stance | `bh_closed_stance_pct` | % | – | measured | 5 |  |
| Backhands with the left hand still on the racket at contact | `bh_off_hand_on_pct` | % | low | measured | 5 | one-handed backhand: the left hand should let go before contact |
| Forehand swing time | `fh_swing_s` | s | – | measured | 5 |  |
| Backhand swing time | `bh_swing_s` | s | – | measured | 5 |  |

### Session

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Recording length | `duration_min` | min | – | measured | 1 |  |
| My shots seen | `my_shots` | count | – | measured | 1 |  |
| Ball tracked (data quality) | `ball_tracked_pct` | % | high | measured | 1 |  |

### Score

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Games won | `games_won` | count | – | told to the coach | 1 |  |
| Games lost | `games_lost` | count | – | told to the coach | 1 |  |
| Sets won | `sets_won` | count | – | told to the coach | 1 |  |
| Sets lost | `sets_lost` | count | – | told to the coach | 1 |  |
| Match won (1) or lost (0) | `match_won` | 0/1 | high | told to the coach | 1 |  |
| Break points won | `break_points_won` | count | high | told to the coach | 1 |  |
| Break point chances | `break_points_chances` | count | high | told to the coach | 1 |  |
| Break points saved | `break_points_saved` | count | high | told to the coach | 1 |  |
| Break points faced | `break_points_faced` | count | low | told to the coach | 1 |  |
| Tie-breaks won | `tiebreaks_won` | count | high | told to the coach | 1 |  |
| Tie-breaks played | `tiebreaks_played` | count | – | told to the coach | 1 |  |

### How it felt

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Effort, RPE | `rpe` | 1-10 | – | told to the coach | 1 |  |
| Energy before playing | `energy` | 1-10 | high | told to the coach | 1 |  |
| Focus and composure | `focus` | 1-10 | high | told to the coach | 1 |  |
| Confidence in the forehand | `confidence_fh` | 1-10 | high | told to the coach | 1 |  |
| Confidence in the backhand | `confidence_bh` | 1-10 | high | told to the coach | 1 |  |
| Confidence in the serve | `confidence_serve` | 1-10 | high | told to the coach | 1 |  |

### Context

| Metric | Property | Unit | Better | Source | Min. sample | Note |
|---|---|---|---|---|---|---|
| Opponent level (NTRP, e.g. 3.5) | `opponent_level` | NTRP | – | told to the coach | 1 |  |
| Wind (0 none to 3 strong) | `wind` | 0-3 | – | told to the coach | 1 |  |

