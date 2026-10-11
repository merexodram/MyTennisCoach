"""Find the parts of a recording where a ball is in play.

Most of a two-hour session is walking, collecting balls and changing ends.
Instead of tracking every frame, look at a short burst of frames every couple
of seconds with the ball network only. Where a ball is seen moving, the
surrounding seconds are marked for full tracking.
"""
from __future__ import annotations

import numpy as np

from . import video


def ball_in_flight(blobs: list, min_px: float, max_px: float, need: int = 4) -> bool:
    """True if the strongest blob travels along a smooth path over the burst.

    A ball in play moves every frame and keeps its heading; a false detection
    on a logo, a shoe or a spectator stays put or jumps about.
    """
    pts = [(k, b[0][0], b[0][1]) for k, b in enumerate(blobs) if b]
    if len(pts) < need:
        return False
    steps = []
    for (k0, x0, y0), (k1, x1, y1) in zip(pts[:-1], pts[1:]):
        dt = k1 - k0
        vx, vy = (x1 - x0) / dt, (y1 - y0) / dt
        if min_px < np.hypot(vx, vy) < max_px:
            steps.append((vx, vy))
        else:
            steps.append(None)
    best = run = 0
    prev = None
    for st in steps:                                   # longest run of steps that keep their heading
        if st is None:
            run, prev = 0, None
            continue
        if prev is not None:
            cos = (st[0] * prev[0] + st[1] * prev[1]) / (np.hypot(*st) * np.hypot(*prev))
            run = run + 1 if cos > 0.5 else 1
        else:
            run = 1
        prev = st
        best = max(best, run)
    return best >= need - 1


def merge(active_starts: list[int], n_frames: int, fps: float, period: int,
          pad_s: float, join_s: float) -> list[tuple[int, int]]:
    """Turn active burst positions into padded, merged [start, end) windows."""
    pad, join = int(pad_s * fps), int(join_s * fps)
    windows: list[list[int]] = []
    for s in active_starts:
        a, b = max(0, s - pad), min(n_frames, s + period + pad)
        if windows and a - windows[-1][1] <= join:
            windows[-1][1] = max(windows[-1][1], b)
        else:
            windows.append([a, b])
    return [(a, b) for a, b in windows]


def find_windows(path, info: video.VideoInfo, ball_tracker, court_detector=None, burst: int = 8,
                 period_s: float = 2.0, pad_s: float = 3.0, join_s: float = 4.0, log=print, details: list | None = None
                 ) -> list[tuple[int, int]]:
    """Stretches of the video where a ball is in play, as [start, end) frame pairs.

    With a court detector, a burst only counts if the court is in view, which
    rules out close-ups and crowd shots before the ball network is even run.
    """
    from . import court as court_mod

    period = max(burst + 2, int(round(period_s * info.fps)))
    reader = video.Reader(path)
    scale = info.height / 480.0
    active = []
    starts = list(range(0, max(1, info.frames - burst - 2), period))
    for k, s in enumerate(starts):
        frames = reader.read(s, burst + 2)                 # two extra frames of history
        if len(frames) < 6:
            break
        court_ok = True
        if court_detector is not None:
            H, n_inl, err = court_mod.fit_homography(court_detector.keypoints(frames[0]))
            court_ok = H is not None and n_inl >= 8 and err <= 5.0
        blobs = []
        if court_ok:
            ball_tracker.reset()
            blobs = ball_tracker.infer(frames)[2:]
            if ball_in_flight(blobs, 1.5 * scale, 0.12 * info.width):
                active.append(s)
        if details is not None:
            details.append({"start": s, "court": court_ok, "blobs": blobs})
        if k and k % 200 == 0:
            log(f"  scanning for play: {100 * k // len(starts)}%")
    reader.close()
    ball_tracker.reset()
    return merge(active, info.frames, info.fps, period, pad_s, join_s)
