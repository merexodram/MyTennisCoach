"""The session metrics: what a professional statistician would log, filled
automatically where one camera can see it and by the coach chat where it cannot.

Every metric has one row per session in the table session_metrics, so any
two sessions, or a session and the all-time best, can be compared.

    source 'auto'   measured from the video by the pipeline
    source 'coach'  told to the coach in the review chat (score, how it felt,
                    corrections of what the camera got wrong); overrides 'auto'

The catalogue (METRICS) is documented for humans in docs/METRICS.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import court


@dataclass(frozen=True)
class Metric:
    key: str
    group: str
    label: str
    unit: str          # '%', 'count', 'km/h', 'm', 'deg', 'rpm', 's', 'ratio', '1-10', ...
    better: str | None  # 'high' | 'low' | None (no better direction)
    how: str           # 'auto' | 'estimate' (auto, single-camera estimate) | 'coach' (from the chat)
    min_n: int = 1     # fewest strokes/points before the value is worth comparing
    note: str = ""


def _m(*a, **k):
    return Metric(*a, **k)


METRICS: list[Metric] = [
    # --- Serve ---------------------------------------------------------------
    _m("serves", "Serve", "Serves hit", "count", None, "auto"),
    _m("first_serve_in_pct", "Serve", "1st serve in", "%", "high", "auto", 5),
    _m("second_serve_in_pct", "Serve", "2nd serve in", "%", "high", "auto", 3),
    _m("double_faults", "Serve", "Double faults", "count", "low", "auto"),
    _m("double_fault_pct", "Serve", "Double faults per service point", "%", "low", "auto", 5),
    _m("unreturned_serves", "Serve", "Unreturned serves (aces and serve winners)", "count", "high", "auto"),
    _m("first_serve_won_pct", "Serve", "Points won on 1st serve", "%", "high", "auto", 5,
       "only points whose end the camera saw"),
    _m("second_serve_won_pct", "Serve", "Points won on 2nd serve", "%", "high", "auto", 3),
    _m("first_serve_kmh", "Serve", "1st serve speed, average", "km/h", "high", "estimate", 3),
    _m("first_serve_kmh_max", "Serve", "1st serve speed, fastest", "km/h", "high", "estimate", 3),
    _m("second_serve_kmh", "Serve", "2nd serve speed, average", "km/h", None, "estimate", 3),
    _m("serve_t_pct", "Serve", "Serves to the T", "%", None, "auto", 5),
    _m("serve_wide_pct", "Serve", "Serves wide", "%", None, "auto", 5),
    _m("serve_body_pct", "Serve", "Serves to the body", "%", None, "auto", 5),
    _m("serve_contact_m", "Serve", "Serve contact height", "m", "high", "auto", 3, "from the pose"),
    # --- Return --------------------------------------------------------------
    _m("returns", "Return", "Returns hit", "count", None, "auto"),
    _m("return_in_pct", "Return", "Returns in", "%", "high", "auto", 5),
    _m("return_deep_pct", "Return", "Returns landing deep", "%", "high", "auto", 5),
    _m("return_won_pct", "Return", "Return points won", "%", "high", "auto", 5),
    # --- Rally ---------------------------------------------------------------
    _m("points", "Rally", "Points (rallies) seen", "count", None, "auto"),
    _m("points_won_pct", "Rally", "Points won", "%", "high", "auto", 10, "points whose end the camera saw"),
    _m("rally_avg", "Rally", "Average rally length", "shots", None, "auto", 5),
    _m("rally_max", "Rally", "Longest rally", "shots", "high", "auto"),
    _m("rally_short_pct", "Rally", "Rallies of 0-4 shots", "%", None, "auto", 10),
    _m("rally_mid_pct", "Rally", "Rallies of 5-8 shots", "%", None, "auto", 10),
    _m("rally_long_pct", "Rally", "Rallies of 9+ shots", "%", None, "auto", 10),
    _m("won_short_pct", "Rally", "Points won in 0-4 shot rallies", "%", "high", "auto", 5),
    _m("won_long_pct", "Rally", "Points won in 5+ shot rallies", "%", "high", "auto", 5),
    # --- Groundstrokes -------------------------------------------------------
    _m("forehands", "Groundstrokes", "Forehands", "count", None, "auto"),
    _m("backhands", "Groundstrokes", "Backhands", "count", None, "auto"),
    _m("forehand_share_pct", "Groundstrokes", "Forehand share of groundstrokes", "%", None, "auto", 10),
    _m("fh_in_pct", "Groundstrokes", "Forehands in", "%", "high", "auto", 10),
    _m("bh_in_pct", "Groundstrokes", "Backhands in", "%", "high", "auto", 10),
    _m("fh_kmh", "Groundstrokes", "Forehand speed, average", "km/h", "high", "estimate", 5),
    _m("bh_kmh", "Groundstrokes", "Backhand speed, average", "km/h", "high", "estimate", 5),
    _m("fh_kmh_top", "Groundstrokes", "Forehand speed, top 10 %", "km/h", "high", "estimate", 10),
    _m("bh_kmh_top", "Groundstrokes", "Backhand speed, top 10 %", "km/h", "high", "estimate", 10),
    _m("fh_deep_pct", "Groundstrokes", "Forehands landing deep (last 3 m)", "%", "high", "auto", 10),
    _m("bh_deep_pct", "Groundstrokes", "Backhands landing deep (last 3 m)", "%", "high", "auto", 10),
    _m("short_ball_pct", "Groundstrokes", "My balls landing before the service line", "%", "low", "auto", 10),
    _m("fh_cross_pct", "Groundstrokes", "Forehands cross-court", "%", None, "auto", 10),
    _m("bh_cross_pct", "Groundstrokes", "Backhands cross-court", "%", None, "auto", 10),
    _m("avg_depth_m", "Groundstrokes", "Average landing distance from the net", "m", "high", "auto", 10),
    # --- Ball flight (3D from one camera) -------------------------------------
    _m("fh_net_clear_m", "Ball flight", "Forehand net clearance", "m", None, "estimate", 5,
       "about 0.6-1.2 m is the safe window for rally balls"),
    _m("bh_net_clear_m", "Ball flight", "Backhand net clearance", "m", None, "estimate", 5),
    _m("fh_apex_m", "Ball flight", "Forehand highest point", "m", None, "estimate", 5),
    _m("bh_apex_m", "Ball flight", "Backhand highest point", "m", None, "estimate", 5),
    _m("fh_spin_rpm", "Ball flight", "Forehand spin (+ topspin)", "rpm", None, "estimate", 5,
       "experimental: trust the trend, not the number"),
    _m("bh_spin_rpm", "Ball flight", "Backhand spin (+ topspin, - slice)", "rpm", None, "estimate", 5,
       "experimental"),
    _m("fh_bounce_deg", "Ball flight", "Forehand landing angle", "deg", None, "estimate", 5,
       "steeper = more topspin and kick"),
    _m("bh_bounce_deg", "Ball flight", "Backhand landing angle", "deg", None, "estimate", 5),
    # --- Winners and errors ----------------------------------------------------
    _m("winners", "Errors", "Winners", "count", "high", "auto"),
    _m("unforced_errors", "Errors", "Unforced errors", "count", "low", "auto",
       note="forced/unforced is judged by rule: fast incoming ball or stretched = forced"),
    _m("forced_errors", "Errors", "Forced errors", "count", None, "auto"),
    _m("winner_ue_ratio", "Errors", "Winners / unforced errors", "ratio", "high", "auto", 5),
    _m("ue_per_100", "Errors", "Unforced errors per 100 of my shots", "per 100", "low", "auto", 30),
    _m("errors_net", "Errors", "Errors into the net", "count", "low", "auto"),
    _m("errors_long", "Errors", "Errors long", "count", "low", "auto"),
    _m("errors_wide", "Errors", "Errors wide", "count", "low", "auto"),
    _m("fh_errors", "Errors", "Forehand errors", "count", "low", "auto"),
    _m("bh_errors", "Errors", "Backhand errors", "count", "low", "auto"),
    _m("shots_before_error", "Errors", "My shots in a row before an error (consistency)", "shots", "high", "auto", 3),
    # --- Net -----------------------------------------------------------------
    _m("net_points", "Net", "Points where I came to the net", "count", None, "auto"),
    _m("net_won_pct", "Net", "Net points won", "%", "high", "auto", 3),
    _m("volleys", "Net", "Volleys", "count", None, "auto"),
    # --- Position and movement --------------------------------------------------
    _m("contact_behind_m", "Movement", "Average contact distance behind my baseline", "m", "low", "auto", 10,
       "smaller = taking the ball earlier"),
    _m("inside_baseline_pct", "Movement", "Groundstrokes taken inside the baseline", "%", "high", "auto", 10),
    _m("distance_per_point_m", "Movement", "Distance run per point", "m", None, "auto", 5),
    _m("distance_total_m", "Movement", "Distance run in rallies", "m", None, "auto"),
    _m("rest_position_m", "Movement", "Average position behind my baseline during rallies", "m", "low", "auto", 5),
    # --- Technique (pose) ------------------------------------------------------
    _m("fh_contact_height_m", "Technique", "Forehand contact height", "m", None, "auto", 5),
    _m("bh_contact_height_m", "Technique", "Backhand contact height", "m", None, "auto", 5),
    _m("fh_contact_spread_m", "Technique", "Forehand contact height, spread", "m", "low", "auto", 5,
       "smaller = more repeatable contact"),
    _m("bh_contact_spread_m", "Technique", "Backhand contact height, spread", "m", "low", "auto", 5),
    _m("fh_reach_m", "Technique", "Forehand contact distance from the body", "m", None, "auto", 5),
    _m("bh_reach_m", "Technique", "Backhand contact distance from the body", "m", None, "auto", 5),
    _m("fh_knee_deg", "Technique", "Forehand knee angle at loading", "deg", "low", "auto", 5, "smaller = deeper bend"),
    _m("bh_knee_deg", "Technique", "Backhand knee angle at loading", "deg", "low", "auto", 5),
    _m("fh_open_stance_pct", "Technique", "Forehands from an open or semi-open stance", "%", None, "auto", 5),
    _m("bh_closed_stance_pct", "Technique", "Backhands from a closed or neutral stance", "%", None, "auto", 5),
    _m("bh_off_hand_on_pct", "Technique", "Backhands with the left hand still on the racket at contact", "%", "low",
       "auto", 5, "one-handed backhand: the left hand should let go before contact"),
    _m("fh_swing_s", "Technique", "Forehand swing time", "s", None, "auto", 5),
    _m("bh_swing_s", "Technique", "Backhand swing time", "s", None, "auto", 5),
    # --- Session ----------------------------------------------------------------
    _m("duration_min", "Session", "Recording length", "min", None, "auto"),
    _m("my_shots", "Session", "My shots seen", "count", None, "auto"),
    _m("ball_tracked_pct", "Session", "Ball tracked (data quality)", "%", "high", "auto"),
    # --- Told to the coach --------------------------------------------------------
    _m("games_won", "Score", "Games won", "count", None, "coach"),
    _m("games_lost", "Score", "Games lost", "count", None, "coach"),
    _m("sets_won", "Score", "Sets won", "count", None, "coach"),
    _m("sets_lost", "Score", "Sets lost", "count", None, "coach"),
    _m("match_won", "Score", "Match won (1) or lost (0)", "0/1", "high", "coach"),
    _m("break_points_won", "Score", "Break points won", "count", "high", "coach"),
    _m("break_points_chances", "Score", "Break point chances", "count", "high", "coach"),
    _m("break_points_saved", "Score", "Break points saved", "count", "high", "coach"),
    _m("break_points_faced", "Score", "Break points faced", "count", "low", "coach"),
    _m("tiebreaks_won", "Score", "Tie-breaks won", "count", "high", "coach"),
    _m("tiebreaks_played", "Score", "Tie-breaks played", "count", None, "coach"),
    _m("rpe", "How it felt", "Effort, RPE", "1-10", None, "coach"),
    _m("energy", "How it felt", "Energy before playing", "1-10", "high", "coach"),
    _m("focus", "How it felt", "Focus and composure", "1-10", "high", "coach"),
    _m("confidence_fh", "How it felt", "Confidence in the forehand", "1-10", "high", "coach"),
    _m("confidence_bh", "How it felt", "Confidence in the backhand", "1-10", "high", "coach"),
    _m("confidence_serve", "How it felt", "Confidence in the serve", "1-10", "high", "coach"),
    _m("opponent_level", "Context", "Opponent level (NTRP, e.g. 3.5)", "NTRP", None, "coach"),
    _m("wind", "Context", "Wind (0 none to 3 strong)", "0-3", None, "coach"),
]
BY_KEY = {m.key: m for m in METRICS}
GROUPS = list(dict.fromkeys(m.group for m in METRICS))


# ---------------------------------------------------------------------------

def _rows(con, sql, params=()):
    cur = con.execute(sql, list(params))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _pct(hits, total):
    return (100.0 * hits / total, total) if total else (None, 0)


def _avg(vals):
    v = [x for x in vals if x is not None and x == x]
    return (float(np.mean(v)), len(v)) if v else (None, 0)


def compute(con, sid: int) -> dict:
    """Metric key -> (value, n) for everything the pipeline can measure."""
    shots = _rows(con, """SELECT s.*, p.contact_height_m, p.knee_flex_deg, p.stance, p.off_hand_on_racket,
                                 p.swing_duration_s, p.contact_reach_m
                          FROM shots s LEFT JOIN pose_metrics p USING (shot_id)
                          WHERE s.session_id = ? ORDER BY s.frame""", [sid])
    points = _rows(con, "SELECT * FROM points WHERE session_id = ? ORDER BY seq", [sid])
    se = _rows(con, "SELECT * FROM sessions WHERE session_id = ?", [sid])[0]
    by_point: dict = {}
    for s in shots:
        by_point.setdefault(s["point_id"], []).append(s)
    out: dict = {}

    def put(key, val_n):
        v, n = val_n
        if v is not None:
            out[key] = (float(v), int(n))

    mine = [s for s in shots if s["hitter"] == "me"]
    # An error ends the point. An 'out' mark in the middle of a rally that went
    # on is a tracking mistake and is not counted.
    ended = {ss[-1]["shot_id"] for ss in by_point.values() if ss}
    known = [p for p in points if p["winner"] in ("me", "opponent")]

    # --- Serve: first and second serves from the order of my serves ------------
    serves = [s for s in mine if s["stroke"] == "serve" and s["seq"] == 1]
    first, second = [], []
    prev, first_ids = None, set()
    for s in serves:
        is_second = (prev is not None and prev["shot_id"] in first_ids and prev["in_court"] is False
                     and s["t_s"] - prev["t_s"] < 25.0)
        (second if is_second else first).append(s)
        if not is_second:
            first_ids.add(s["shot_id"])
        prev = s
    put("serves", (len(serves), len(serves)))
    f_seen = [s for s in first if s["in_court"] is not None]
    s_seen = [s for s in second if s["in_court"] is not None]
    put("first_serve_in_pct", _pct(sum(s["in_court"] for s in f_seen), len(f_seen)))
    put("second_serve_in_pct", _pct(sum(s["in_court"] for s in s_seen), len(s_seen)))
    dfs = sum(1 for s in s_seen if not s["in_court"])
    put("double_faults", (dfs, len(s_seen)))
    service_points = sum(1 for s in f_seen if s["in_court"]) + len(s_seen)
    put("double_fault_pct", _pct(dfs, service_points))
    p_of = {p["point_id"]: p for p in points}
    put("unreturned_serves", (sum(1 for s in serves if s["in_court"] and p_of[s["point_id"]]["rally_length"] == 1),
                              len(serves)))

    def won(group):
        ps = [p_of[s["point_id"]] for s in group if s["in_court"] and p_of[s["point_id"]]["winner"]]
        return _pct(sum(p["winner"] == "me" for p in ps), len(ps))
    put("first_serve_won_pct", won(first))
    put("second_serve_won_pct", won(second))
    put("first_serve_kmh", _avg([s["speed_kmh"] for s in first if s["in_court"]]))
    fk = [s["speed_kmh"] for s in first if s["speed_kmh"]]
    if len(fk) >= 1:
        put("first_serve_kmh_max", (max(fk), len(fk)))
    put("second_serve_kmh", _avg([s["speed_kmh"] for s in second]))
    placed = [abs(s["bounce_x_m"]) for s in serves if s["in_court"] and s["bounce_x_m"] is not None]
    if placed:
        n = len(placed)
        put("serve_t_pct", _pct(sum(x < 1.4 for x in placed), n))
        put("serve_wide_pct", _pct(sum(x > 2.7 for x in placed), n))
        put("serve_body_pct", _pct(sum(1.4 <= x <= 2.7 for x in placed), n))
    put("serve_contact_m", _avg([s["contact_height_m"] for s in serves]))

    # --- Return -------------------------------------------------------------
    rets = []
    for pid, ss in by_point.items():
        if ss and ss[0]["hitter"] == "opponent" and ss[0]["stroke"] == "serve" and len(ss) > 1 and ss[1]["hitter"] == "me":
            rets.append(ss[1])
    put("returns", (len(rets), len(rets)))
    rs = [s for s in rets if s["in_court"] is not None]
    put("return_in_pct", _pct(sum(s["in_court"] for s in rs), len(rs)))
    rd = [s for s in rets if s["in_court"] and s["bounce_y_m"] is not None]
    put("return_deep_pct", _pct(sum(abs(s["bounce_y_m"]) > court.HALF_LENGTH - 3.0 for s in rd), len(rd)))
    rp = [p_of[s["point_id"]] for s in rets if p_of[s["point_id"]]["winner"]]
    put("return_won_pct", _pct(sum(p["winner"] == "me" for p in rp), len(rp)))

    # --- Rally --------------------------------------------------------------
    lens = [p["rally_length"] for p in points if p["end_reason"] != "fault"]
    put("points", (len(points), len(points)))
    put("points_won_pct", _pct(sum(p["winner"] == "me" for p in known), len(known)))
    if lens:
        put("rally_avg", (float(np.mean(lens)), len(lens)))
        put("rally_max", (max(lens), len(lens)))
        put("rally_short_pct", _pct(sum(n <= 4 for n in lens), len(lens)))
        put("rally_mid_pct", _pct(sum(5 <= n <= 8 for n in lens), len(lens)))
        put("rally_long_pct", _pct(sum(n >= 9 for n in lens), len(lens)))
    ks = [p for p in known if p["rally_length"] <= 4]
    kl = [p for p in known if p["rally_length"] >= 5]
    put("won_short_pct", _pct(sum(p["winner"] == "me" for p in ks), len(ks)))
    put("won_long_pct", _pct(sum(p["winner"] == "me" for p in kl), len(kl)))

    # --- Groundstrokes and flight ----------------------------------------------
    gs = {"fh": [s for s in mine if s["stroke"] == "forehand"], "bh": [s for s in mine if s["stroke"] == "backhand"]}
    put("forehands", (len(gs["fh"]), len(gs["fh"])))
    put("backhands", (len(gs["bh"]), len(gs["bh"])))
    put("forehand_share_pct", _pct(len(gs["fh"]), len(gs["fh"]) + len(gs["bh"])))
    for k, g in gs.items():
        seen = [s for s in g if s["in_court"] is not None]
        put(f"{k}_in_pct", _pct(sum(s["in_court"] for s in seen), len(seen)))
        sp = sorted(s["speed_kmh"] for s in g if s["speed_kmh"])
        put(f"{k}_kmh", _avg(sp))
        if len(sp) >= 3:
            top = sp[int(0.9 * (len(sp) - 1)):]
            put(f"{k}_kmh_top", (float(np.mean(top)), len(sp)))
        landed = [s for s in g if s["in_court"] and s["bounce_y_m"] is not None]
        put(f"{k}_deep_pct", _pct(sum(abs(s["bounce_y_m"]) > court.HALF_LENGTH - 3.0 for s in landed), len(landed)))
        dirs = [s["direction"] for s in g if s["direction"]]
        put(f"{k}_cross_pct", _pct(sum(d == "cross" for d in dirs), len(dirs)))
        put(f"{k}_net_clear_m", _avg([s["net_clearance_m"] for s in g]))
        put(f"{k}_apex_m", _avg([s["apex_m"] for s in g]))
        put(f"{k}_spin_rpm", _avg([s["spin_rpm"] for s in g]))
        put(f"{k}_bounce_deg", _avg([s["bounce_angle_deg"] for s in g]))
        put(f"{k}_errors", (sum(1 for s in g if s["shot_id"] in ended and str(s["outcome"]).startswith("error")), len(g)))
        put(f"{k}_contact_height_m", _avg([s["contact_height_m"] for s in g]))
        h = [s["contact_height_m"] for s in g if s["contact_height_m"] is not None]
        if len(h) >= 3:
            put(f"{k}_contact_spread_m", (float(np.std(h, ddof=1)), len(h)))
        put(f"{k}_reach_m", _avg([s["contact_reach_m"] for s in g]))
        put(f"{k}_knee_deg", _avg([s["knee_flex_deg"] for s in g]))
        put(f"{k}_swing_s", _avg([s["swing_duration_s"] for s in g]))
    st = [s["stance"] for s in gs["fh"] if s["stance"]]
    put("fh_open_stance_pct", _pct(sum(x in ("open", "semi_open") for x in st), len(st)))
    st = [s["stance"] for s in gs["bh"] if s["stance"]]
    put("bh_closed_stance_pct", _pct(sum(x in ("closed", "neutral") for x in st), len(st)))
    oh = [s["off_hand_on_racket"] for s in gs["bh"] if s["off_hand_on_racket"] is not None]
    put("bh_off_hand_on_pct", _pct(sum(bool(x) for x in oh), len(oh)))
    landed = [s for s in gs["fh"] + gs["bh"] if s["in_court"] and s["bounce_y_m"] is not None]
    put("short_ball_pct", _pct(sum(abs(s["bounce_y_m"]) < court.SERVICE for s in landed), len(landed)))
    put("avg_depth_m", _avg([abs(s["bounce_y_m"]) for s in landed]))

    # --- Winners and errors ---------------------------------------------------
    last_of = {pid: ss[-1] for pid, ss in by_point.items() if ss}
    my_end = [(p, last_of.get(p["point_id"])) for p in points]
    my_end = [(p, s) for p, s in my_end if s is not None and s["hitter"] == "me"]
    w = sum(1 for p, s in my_end if s["outcome"] == "winner")
    ue = sum(1 for p, s in my_end if p["end_reason"] == "unforced_error")
    fe = sum(1 for p, s in my_end if p["end_reason"] == "forced_error")
    put("winners", (w, len(mine)))
    put("unforced_errors", (ue, len(mine)))
    put("forced_errors", (fe, len(mine)))
    if ue:
        put("winner_ue_ratio", (w / ue, w + ue))
    put("ue_per_100", _pct(ue, len(mine)))
    for key, out_name in (("errors_net", "error_net"), ("errors_long", "error_long"), ("errors_wide", "error_wide")):
        put(key, (sum(1 for s in mine if s["shot_id"] in ended and s["outcome"] == out_name), len(mine)))
    runs, count = [], 0
    for s in mine:
        if s["stroke"] == "serve":
            continue
        if s["shot_id"] in ended and str(s["outcome"]).startswith("error"):
            runs.append(count)
            count = 0
        else:
            count += 1
    if runs:
        put("shots_before_error", (float(np.mean(runs)), len(runs)))

    # --- Net -------------------------------------------------------------------
    net_pts = [pid for pid, ss in by_point.items()
               if any(s["hitter"] == "me" and s["stroke"] != "serve" and s["contact_y_m"] is not None
                      and abs(s["contact_y_m"]) < court.SERVICE for s in ss)]
    put("net_points", (len(net_pts), len(points)))
    nk = [p_of[pid] for pid in net_pts if p_of[pid]["winner"]]
    put("net_won_pct", _pct(sum(p["winner"] == "me" for p in nk), len(nk)))
    put("volleys", (sum(1 for s in mine if s["stroke"] == "volley"
                        or (s["stroke"] != "serve" and s["contact_y_m"] is not None and abs(s["contact_y_m"]) < 4.5)),
                    len(mine)))

    # --- Position and movement --------------------------------------------------
    cy = [abs(s["contact_y_m"]) for s in gs["fh"] + gs["bh"] if s["contact_y_m"] is not None]
    if cy:
        put("contact_behind_m", (float(np.mean(cy)) - court.HALF_LENGTH, len(cy)))
        put("inside_baseline_pct", _pct(sum(y < court.HALF_LENGTH for y in cy), len(cy)))
    dist = [p["me_distance_m"] for p in points if p.get("me_distance_m") is not None]
    put("distance_per_point_m", _avg(dist))
    if dist:
        put("distance_total_m", (float(np.sum(dist)), len(dist)))
    put("rest_position_m", _avg([p.get("me_behind_baseline_m") for p in points]))

    # --- Session ------------------------------------------------------------------
    if se.get("duration_s"):
        put("duration_min", (se["duration_s"] / 60.0, 1))
    put("my_shots", (len(mine), len(mine)))
    try:
        q = json.loads(se.get("notes") or "{}").get("quality", {})
        if q.get("ball_tracked_pct") is not None:
            put("ball_tracked_pct", (q["ball_tracked_pct"], 1))
    except Exception:
        pass
    return out


def store(con, sid: int) -> int:
    """Recompute the automatic metrics of a session; coach entries are kept."""
    vals = compute(con, sid)
    con.execute("DELETE FROM session_metrics WHERE session_id = ? AND source = 'auto'", [sid])
    coach = {r[0] for r in con.execute("SELECT metric FROM session_metrics WHERE session_id = ? AND source = 'coach'",
                                       [sid]).fetchall()}
    for k, (v, n) in vals.items():
        if k not in coach:
            con.execute("INSERT INTO session_metrics VALUES (?,?,?,?,?)", [sid, k, v, n, "auto"])
    return len(vals)


SESSION_FIELDS = ("played_on", "kind", "opponent", "surface", "location", "player")


def apply_coach_input(con, sid: int, path: Path) -> list[str]:
    """Store what was told in the review chat: outputs/coach/session_NNNN/coach_input.json

        {"session": {"kind": "match", "opponent": "Ali", "surface": "clay", "played_on": "2026-10-14"},
         "metrics": {"games_won": 6, "games_lost": 4, "double_faults": 3, "rpe": 7},
         "note": "windy, new strings"}

    Metric values given here replace the automatic ones of the same key.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    done = []
    for k, v in (data.get("session") or {}).items():
        if k in SESSION_FIELDS and v is not None:
            con.execute(f"UPDATE sessions SET {k} = ? WHERE session_id = ?", [v, sid])
            done.append(f"{k}={v}")
    for k, v in (data.get("metrics") or {}).items():
        if v is None:
            continue
        if k not in BY_KEY:
            print(f"  unknown metric '{k}' skipped (see docs/METRICS.md)")
            continue
        con.execute("DELETE FROM session_metrics WHERE session_id = ? AND metric = ?", [sid, k])
        con.execute("INSERT INTO session_metrics VALUES (?,?,?,?,?)", [sid, k, float(v), 1, "coach"])
        done.append(f"{k}={v}")
    if data.get("note"):
        row = con.execute("SELECT notes FROM sessions WHERE session_id = ?", [sid]).fetchone()
        try:
            notes = json.loads(row[0] or "{}")
        except Exception:
            notes = {"note": row[0]}
        notes["coach_note"] = data["note"]
        con.execute("UPDATE sessions SET notes = ? WHERE session_id = ?", [json.dumps(notes), sid])
    return done


def table(con, include_reference: bool = False) -> tuple[list[dict], dict]:
    """All sessions and their metrics: (sessions, {session_id: {metric: (value, n, source)}})."""
    where = "" if include_reference else "WHERE kind <> 'reference'"
    sessions = _rows(con, f"SELECT session_id, played_on, kind, source, opponent, surface, location, video_file "
                          f"FROM sessions {where} ORDER BY played_on, session_id")
    vals: dict = {s["session_id"]: {} for s in sessions}
    for sid, k, v, n, src in con.execute("SELECT session_id, metric, value, n, source FROM session_metrics").fetchall():
        if sid in vals:
            vals[sid][k] = (v, n, src)
    return sessions, vals


def best(vals: dict, key: str):
    """(session_id, value) of the all-time best for a metric, among sessions with enough data."""
    m = BY_KEY[key]
    if m.better is None:
        return None
    cands = [(sid, d[key][0]) for sid, d in vals.items()
             if key in d and d[key][0] is not None and (d[key][2] == "coach" or (d[key][1] or 0) >= m.min_n)]
    if not cands:
        return None
    return (max if m.better == "high" else min)(cands, key=lambda c: c[1])
