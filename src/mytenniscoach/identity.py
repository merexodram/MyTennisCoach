"""Which of the two players is "me".

The user clicks on themself once (calibrate.bat). The colours of their
clothing at that moment become the reference. Players change ends during a
match, so for every rally the near and the far player are both compared with
the reference, and the closer match is "me" for that rally.
"""
from __future__ import annotations

import cv2
import numpy as np

from . import video


def clothing(frame: np.ndarray, box) -> np.ndarray | None:
    """Colour signature of a player: shirt and shorts, as a normalised histogram."""
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    w, h = x2 - x1, y2 - y1
    if w < 4 or h < 8:
        return None
    # Middle of the body, away from the background at the edges and from head and feet.
    xa, xb = int(x1 + 0.28 * w), int(x1 + 0.72 * w)
    ya, yb = int(y1 + 0.18 * h), int(y1 + 0.62 * h)
    patch = frame[max(0, ya): max(0, yb), max(0, xa): max(0, xb)]
    if patch.size == 0:
        return None
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256]).ravel()
    total = hist.sum()
    return (hist / total).astype(np.float32) if total > 0 else None


def similarity(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """1 = identical colours, 0 = nothing in common."""
    if a is None or b is None:
        return 0.0
    return float(np.sqrt(a * b).sum())                 # Bhattacharyya coefficient


def reference(path, boxes_per_frame: list, frame_index: int, point) -> np.ndarray | None:
    """Clothing signature of the person clicked at `point` in frame `frame_index`."""
    reader = video.Reader(path)
    frames = reader.read(frame_index, 1)
    reader.close()
    if not frames:
        return None
    px, py = point
    best, best_area = None, float("inf")
    # The tracks may not include this exact frame: look at neighbouring frames too.
    for f in sorted(range(len(boxes_per_frame)), key=lambda g: abs(g - frame_index))[:31]:
        for b in boxes_per_frame[f]:
            if b[0] <= px <= b[2] and b[1] <= py <= b[3]:
                area = (b[2] - b[0]) * (b[3] - b[1])
                if area < best_area:
                    best, best_area = b, area
        if best is not None:
            break
    if best is None:                                   # no detection there: use a box around the click
        best = (px - 30, py - 60, px + 30, py + 60)
    return clothing(frames[0], best)


def me_sides(path, chosen: list, shots: list, ref: np.ndarray | None, fps: float, samples: int = 6) -> dict:
    """For each rally number, 'near' or 'far': the side "me" is playing on.

    Returns {} when there is no reference.
    """
    if ref is None or not shots:
        return {}
    reader = video.Reader(path)
    out: dict = {}
    for rally in sorted({s.rally for s in shots}):
        rs = [s for s in shots if s.rally == rally]
        a, b = rs[0].frame, rs[-1].frame + int(fps)
        picks = np.linspace(a, min(b, len(chosen) - 1), samples).astype(int)
        score = {"near": [], "far": []}
        for f in picks:
            got = reader.read(int(f), 1)
            if not got:
                continue
            for side in ("near", "far"):
                p = chosen[int(f)].get(side)
                if p is not None:
                    score[side].append(similarity(ref, clothing(got[0], p[0])))
        near = float(np.mean(score["near"])) if score["near"] else 0.0
        far = float(np.mean(score["far"])) if score["far"] else 0.0
        out[rally] = {"side": "near" if near >= far else "far", "near": near, "far": far}
    reader.close()
    return out
