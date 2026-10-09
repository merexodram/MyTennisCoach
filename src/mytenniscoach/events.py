"""Turn per-frame tracks into tennis events: hits, bounces, shots, rallies.

Single-camera reasoning, behind-the-baseline view:

* The ball's image y grows as it travels towards the camera and shrinks as
  it travels away. A hit is where that direction reverses near a player.
* A bounce is a sharp kink in the image trajectory between two hits. At the
  bounce the ball is on the ground, so its image position maps exactly to
  court metres through the homography; in flight it does not.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import court


@dataclass
class Shot:
    frame: int
    hitter: str                      # 'near' | 'far'
    contact_xy_m: tuple | None       # hitter's feet on court
    ball_px: tuple
    bounce_frame: int | None = None
    bounce_xy_m: tuple | None = None
    in_court: bool | None = None
    speed_kmh: float | None = None
    stroke: str = "unknown"
    direction: str | None = None
    depth: str | None = None
    outcome: str = "in_play"
    confidence: float = 0.5
    rally: int = 0
    seq: int = 0


def _vy(y: np.ndarray, half: int = 2) -> np.ndarray:
    """Vertical image speed (px/frame), NaN where the ball is not tracked."""
    v = np.full(len(y), np.nan)
    for i in range(half, len(y) - half):
        if np.isfinite(y[i - half]) and np.isfinite(y[i + half]):
            v[i] = (y[i + half] - y[i - half]) / (2.0 * half)
    return v


def _runs(v: np.ndarray, min_speed: float, min_len: int = 3, bridge: int = 3) -> list[dict]:
    """Stretches where the ball keeps moving down the screen (+1) or up it (-1)."""
    runs: list[dict] = []
    for i, val in enumerate(v):
        if not np.isfinite(val) or abs(val) < min_speed:
            continue
        sign = 1 if val > 0 else -1
        if runs and runs[-1]["sign"] == sign and i - runs[-1]["end"] <= bridge + 1:
            runs[-1]["end"] = i
            runs[-1]["n"] += 1
        else:
            runs.append({"sign": sign, "start": i, "end": i, "n": 1})
    return [r for r in runs if r["n"] >= min_len]


def _in_zone(ball_xy, box, reach_x: float, up: float, down: float) -> bool:
    if box is None or not np.isfinite(ball_xy[0]):
        return False
    b = box[0]
    bh = b[3] - b[1]
    return (b[0] - reach_x * bh <= ball_xy[0] <= b[2] + reach_x * bh
            and b[1] - up * bh <= ball_xy[1] <= b[3] + down * bh)


def find_hits(ball_px: np.ndarray, players: list[dict], Hs: list, fps: float, frame_h: int):
    """Hits are reversals of the ball's vertical image direction next to a player,
    after which the ball actually travels to the other half.

    Returns (hits, far_bounces): hits as (frame, side); far_bounces as frames where
    the ball turned upwards on screen away from the near player (a bounce on the
    far side of the net).
    """
    y = ball_px[:, 1]
    scale = frame_h / 480.0
    runs = _runs(_vy(y), min_speed=0.6 * scale)
    max_gap = int(fps * 0.9)
    cands: list[tuple[int, str]] = []
    far_bounces: list[int] = []

    for r1, r2 in zip(runs[:-1], runs[1:]):
        if r1["sign"] == r2["sign"] or r2["start"] - r1["end"] > max_gap:
            continue
        lo, hi = max(0, r1["end"] - 2), min(len(y) - 1, r2["start"] + 2)
        window = np.arange(lo, hi + 1)
        valid = window[np.isfinite(y[window])]
        if len(valid) == 0:
            continue
        H = Hs[r1["end"]]
        if H is None:
            continue
        net_y = float(court.to_image(H, [(0.0, 0.0)])[0][1])
        near_base_y = float(court.to_image(H, [(0.0, court.HALF_LENGTH)])[0][1])

        if r1["sign"] > 0:                       # was coming down the screen, now going up
            t = int(valid[np.argmax(y[valid])])
            near = any(_in_zone(ball_px[f], players[f].get("near"), 1.5, 1.0, 0.5)
                       for f in (r1["end"], t, r2["start"]))
            seg = y[r2["start"]: r2["end"] + 1]
            crosses = np.nanmin(seg) < net_y - 2 * scale
            if near and crosses:
                cands.append((t, "near"))
            elif not near and y[t] < net_y:
                far_bounces.append(t)
        else:                                    # was going up the screen, now coming down
            t = int(valid[np.argmin(y[valid])])
            far = any(_in_zone(ball_px[f], players[f].get("far"), 2.0, 1.5, 1.0)
                      for f in (r1["end"], t, r2["start"]))
            # Follow the ball until it turns again: did it come over the net?
            seg = y[r2["start"]: r2["end"] + 1]
            crosses = np.nanmax(seg) > net_y + 0.2 * (near_base_y - net_y)
            if far and crosses:
                cands.append((t, "far"))

    hits: list[tuple[int, str]] = []
    for t, side in sorted(cands):
        if hits and t - hits[-1][0] < fps * 0.5:
            continue                             # two hits cannot be this close
        hits.append((t, side))
    return hits, far_bounces


def find_bounce(ball_px: np.ndarray, Hs: list, start: int, end: int, fps: float,
                target_sign: float, hints: list[int], scale: float) -> int | None:
    """Where the ball lands between two hits.

    A bounce is a kink in the image path: the ball stops falling on screen.
    Only points that map into the target half of the court are considered.
    """
    lo, hi = start + int(fps * 0.16), end - int(fps * 0.08)
    y = ball_px[:, 1]
    best, best_k = None, 0.0
    for i in range(max(lo, 2), min(hi, len(y) - 2)):
        if not (np.isfinite(y[i - 2]) and np.isfinite(y[i]) and np.isfinite(y[i + 2])) or Hs[i] is None:
            continue
        bx, by = court.to_court(Hs[i], [ball_px[i]])[0]
        depth = by * target_sign
        if not (0.3 < depth < court.HALF_LENGTH + 4.0 and abs(bx) < court.HALF_DOUBLES + 3.0):
            continue
        kink = (y[i] - y[i - 2]) / 2.0 - (y[i + 2] - y[i]) / 2.0
        if any(abs(i - h) <= 2 for h in hints):
            kink += 2.0 * scale                  # agrees with a direction reversal
        if kink > best_k:
            best, best_k = i, kink
    need = (0.8 if target_sign < 0 else 2.0) * scale
    return best if best_k > need else None


def _nearby(players: list[dict], f: int, side: str, reach: int = 6):
    """The player's box at frame f, or the closest frame where it is known."""
    for d in range(reach + 1):
        for g in (f - d, f + d):
            if 0 <= g < len(players) and players[g].get(side) is not None:
                return players[g][side]
    return None


def build_shots(ball_px: np.ndarray, players: list[dict], Hs: list, fps: float, frame_h: int,
                hands: dict | None = None) -> list[Shot]:
    hands = hands or {"near": "right", "far": "right"}
    hits, far_bounces = find_hits(ball_px, players, Hs, fps, frame_h)
    scale = frame_h / 480.0
    shots: list[Shot] = []
    rally, seq = 0, 0
    for n, (f, side) in enumerate(hits):
        nxt = hits[n + 1][0] if n + 1 < len(hits) else min(len(ball_px) - 3, f + int(fps * 2.5))
        new_rally = n == 0 or f - hits[n - 1][0] > fps * 3.5
        if new_rally:
            rally += 1
            seq = 0
        seq += 1
        p = _nearby(players, f, side)
        s = Shot(frame=f, hitter=side, contact_xy_m=p[1] if p else None,
                 ball_px=tuple(float(v) for v in ball_px[f]), rally=rally, seq=seq)

        # Stroke: serve if first in rally and struck well above the head; otherwise
        # forehand/backhand from which side of the body the ball is on.
        if p is not None:
            b = p[0]
            cx = (b[0] + b[2]) / 2.0
            if seq == 1 and ball_px[f, 1] < b[1] + 0.15 * (b[3] - b[1]):
                s.stroke = "serve"
            else:
                ball_right = ball_px[f, 0] > cx
                # Near player has their back to the camera; far player faces it.
                right_is_forehand = (hands[side] == "right") == (side == "near")
                s.stroke = "forehand" if ball_right == right_is_forehand else "backhand"

        target_sign = -1.0 if side == "near" else 1.0
        b_f = find_bounce(ball_px, Hs, f, nxt, fps, target_sign,
                          far_bounces if side == "near" else [], scale)
        H = Hs[b_f] if b_f is not None else None
        if b_f is not None and H is not None:
            bx, by = court.to_court(H, [ball_px[b_f]])[0]
            s.bounce_frame, s.bounce_xy_m = b_f, (float(bx), float(by))
            on_far_side = by * target_sign > 0
            s.in_court = bool(on_far_side and abs(bx) <= court.HALF_SINGLES + 0.05
                              and abs(by) <= court.HALF_LENGTH + 0.05)
            margins = [court.HALF_SINGLES - abs(bx), court.HALF_LENGTH - abs(by)]
            if s.stroke == "serve" and s.contact_xy_m is not None:
                # A serve must land in the diagonally opposite service box.
                box_sign = -1.0 if s.contact_xy_m[0] > 0 else 1.0
                s.in_court = bool(s.in_court and abs(by) <= court.SERVICE + 0.05 and bx * box_sign >= -0.05)
                margins += [court.SERVICE - abs(by), bx * box_sign]
            depth_m = abs(by)
            s.depth = "short" if depth_m < court.SERVICE else ("mid" if depth_m < 9.0 else "deep")
            if s.contact_xy_m is not None:
                dx = bx - s.contact_xy_m[0]
                dist = float(np.hypot(dx, by - s.contact_xy_m[1]))
                dt = (b_f - f) / fps
                if dt > 0.15:
                    s.speed_kmh = dist / dt * 3.6
                if abs(bx) < 1.2:
                    s.direction = "middle"
                else:
                    s.direction = "cross" if (s.contact_xy_m[0] * bx < 0) else "line"
            if not on_far_side:
                s.outcome = "error_net"
            elif not s.in_court and s.stroke == "serve":
                s.outcome = "fault"
            elif not s.in_court:
                s.outcome = "error_long" if abs(by) > court.HALF_LENGTH else "error_wide"
            # One pixel is 0.2 to 0.3 m at the far baseline: near a line, the call is a guess.
            s.confidence = 0.5 if min(abs(m) for m in margins) < 0.4 else 0.8
        shots.append(s)
    # Last shot of each rally that landed in and was not returned is a winner.
    for i, s in enumerate(shots):
        last_in_rally = i == len(shots) - 1 or shots[i + 1].rally != s.rally
        if last_in_rally and s.in_court:
            s.outcome = "winner"
    return shots
