"""Which of the two players is "me".

The user clicks on themself once (calibrate.bat or calibrate.command, or the
coach marks the click). Players change ends during a match, so for every rally
the near and the far player are compared.

Main method: the colour of the shorts. A pose model finds hips and knees, and
the colour is sampled on the upper thighs, where the shorts are, away from the
court behind the player. Shirts are often alike (two black shirts), and a
whole-body colour histogram mostly measures how big and sharp a player is:
the near player always looks more like a near reference. So the reference
frame itself teaches the difference: the colour of my shorts minus the
opponent's shorts there gives a direction, and in every later frame the
near-minus-far colour difference is projected on it. Several frames per rally
vote. Lightness is ignored (distance and lighting change it), only the
colour (Lab a*, b*) counts.

Fallback without a pose model: clothing histograms as before.
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


def shorts_colour(frame: np.ndarray, box, pose) -> np.ndarray | None:
    """Median colour (Lab a*, b*) of the shorts of the player in `box`, or None."""
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    h = y2 - y1
    if h < 12:
        return None
    pad = 0.15 * h
    X1, Y1 = int(max(0, x1 - pad)), int(max(0, y1 - pad))
    crop = frame[Y1: int(y2 + pad), X1: int(x2 + pad)]
    if crop.size == 0:
        return None
    scale = 256.0 / crop.shape[0]
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    kp = pose.poses([crop])[0]
    if kp is None:
        return None
    px = []
    for hip, knee in ((11, 13), (12, 14)):
        if kp[hip, 2] > 0.3 and kp[knee, 2] > 0.3:
            for t in np.linspace(0.15, 0.55, 9):
                q = kp[hip, :2] + (kp[knee, :2] - kp[hip, :2]) * t
                xi, yi = int(q[0]), int(q[1])
                if 0 <= yi < crop.shape[0] and 0 <= xi < crop.shape[1]:
                    px.append(crop[yi, xi])
    if len(px) < 4:
        return None
    lab = cv2.cvtColor(np.uint8(px).reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    return np.median(lab[:, 1:], axis=0) - 128.0


def similarity(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """1 = identical colours, 0 = nothing in common."""
    if a is None or b is None:
        return 0.0
    return float(np.sqrt(a * b).sum())                 # Bhattacharyya coefficient


def reference(path, boxes_per_frame: list, frame_index: int, point, chosen: list | None = None, pose=None,
              detector=None, H=None):
    """What "me" looks like, from the click at `point` in frame `frame_index`.

    Returns a dict: "hist" (clothing histogram) and, with a pose model and the
    opponent visible in the same frame, "dir" (my shorts colour minus the
    opponent's, the direction that tells us apart). None if nothing is found.

    The click may fall between rallies, where the tracks hold no players, so
    the people in the clicked frame itself are detected when a detector is given.
    """
    reader = video.Reader(path)
    frames = reader.read(frame_index, 1)
    reader.close()
    if not frames:
        return None
    frame = frames[0]
    px, py = point

    def contains(b):
        return b[0] <= px <= b[2] and b[1] <= py <= b[3]

    def area(b):
        return (b[2] - b[0]) * (b[3] - b[1])

    best, other = None, None
    if detector is not None:
        found = [b for b in detector.people_batch([frame])[0]]
        if H is not None:                              # only people standing on or around the court
            from . import court as _court
            keep = []
            for b in found:
                x, y = _court.to_court(H, [((b[0] + b[2]) / 2, b[3])])[0]
                if abs(x) < 8.0 and abs(y) < 18.0:
                    keep.append((b, y))
        else:
            keep = [(b, 0.0) for b in found]
        mine = [k for k in keep if contains(k[0])]
        if not mine and keep:                          # a click just beside the box: nearest person
            d = [np.hypot((k[0][0] + k[0][2]) / 2 - px, (k[0][1] + k[0][3]) / 2 - py) for k in keep]
            j = int(np.argmin(d))
            if d[j] < 1.5 * (keep[j][0][2] - keep[j][0][0]) + 20:
                mine = [keep[j]]
        if mine:
            me_b, me_y = min(mine, key=lambda k: area(k[0]))
            best = me_b
            rest = [k for k in keep if k[0] is not me_b]
            opposite = [k for k in rest if np.sign(k[1]) != np.sign(me_y)] if H is not None else []
            pool = opposite or rest
            if pool:
                other = max(pool, key=lambda k: area(k[0]))[0]
    if best is None:
        # The tracks around the clicked frame.
        for f in sorted(range(len(boxes_per_frame)), key=lambda g: abs(g - frame_index))[:31]:
            hits = [b for b in boxes_per_frame[f] if contains(b)]
            if hits:
                best = min(hits, key=area)
                break
    if best is None:                                   # no detection there: use a box around the click
        best = (px - 30, py - 60, px + 30, py + 60)
    if other is None and chosen is not None and 0 <= frame_index < len(chosen):
        for side in ("near", "far"):
            p = chosen[frame_index].get(side)
            if p is not None and not contains(p[0]):
                other = p[0]
    ref = {"hist": clothing(frame, best)}
    if pose is not None and other is not None:
        mine_c = shorts_colour(frame, best, pose)
        theirs = shorts_colour(frame, other, pose)
        if mine_c is not None and theirs is not None and np.linalg.norm(mine_c - theirs) > 2.0:
            ref["dir"] = (mine_c - theirs).astype(np.float32)
            ref["me_colour"], ref["other_colour"] = mine_c, theirs
    return ref if ref["hist"] is not None or "dir" in ref else None


def me_sides(path, chosen: list, shots: list, ref, fps: float, samples: int = 6, pose=None) -> dict:
    """For each rally number: {"side": "near" | "far", "near": score, "far": score, "sure": bool}.

    Returns {} when there is no reference.
    """
    if ref is None or not shots:
        return {}
    if not isinstance(ref, dict):                      # old-style reference: a histogram
        ref = {"hist": ref}
    use_dir = "dir" in ref and pose is not None
    reader = video.Reader(path)
    raw: dict = {}
    for rally in sorted({s.rally for s in shots}):
        rs = [s for s in shots if s.rally == rally]
        a, b = rs[0].frame, rs[-1].frame + int(fps)
        picks = np.linspace(a, min(b, len(chosen) - 1), samples).astype(int)
        votes, near_s, far_s = [], [], []
        for f in picks:
            got = reader.read(int(f), 1)
            if not got:
                continue
            pn, pf = chosen[int(f)].get("near"), chosen[int(f)].get("far")
            if use_dir:
                if pn is None or pf is None:
                    continue
                cn, cf = shorts_colour(got[0], pn[0], pose), shorts_colour(got[0], pf[0], pose)
                if cn is None or cf is None:
                    continue
                votes.append(cn - cf)
            else:
                if pn is not None:
                    near_s.append(similarity(ref["hist"], clothing(got[0], pn[0])))
                if pf is not None:
                    far_s.append(similarity(ref["hist"], clothing(got[0], pf[0])))
        if use_dir and votes:
            raw[rally] = {"vec": np.median(np.array(votes), axis=0), "n": len(votes)}
        elif near_s or far_s:
            near = float(np.mean(near_s)) if near_s else 0.0
            far = float(np.mean(far_s)) if far_s else 0.0
            raw[rally] = {"side": "near" if near >= far else "far", "near": near, "far": far,
                          "score": near - far, "n": len(near_s) + len(far_s)}
    reader.close()
    if use_dir:
        vecs = [r["vec"] for r in raw.values() if "vec" in r]
        if vecs:
            # Near-minus-far colour per rally is +D or -D, D = my shorts minus the
            # opponent's. Its main axis over the whole match is D; the clicked
            # frame only decides the sign.
            V = np.array(vecs, dtype=np.float64)
            w, U = np.linalg.eigh(V.T @ V)
            D = U[:, int(np.argmax(w))]
            if float(np.dot(D, ref["dir"])) < 0:
                D = -D
            for k, r in raw.items():
                if "vec" in r:
                    v = float(np.dot(r.pop("vec"), D))
                    r.update({"side": "near" if v > 0 else "far", "near": max(v, 0.0), "far": max(-v, 0.0),
                              "score": v})
            raw = {k: r for k, r in raw.items() if "score" in r}
            ratio = float(w.max() / max(w.min(), 1e-9))
            raw["_axis"] = {"D": D.tolist(), "separation": ratio}
    axis = raw.pop("_axis", None)
    out = _smooth(raw)
    if axis is not None:
        out["_axis"] = axis
    return out


def _smooth(raw: dict) -> dict:
    """Players only change ends between games, so a rally whose call is weak
    follows its neighbours (two before and two after)."""
    if not raw:
        return raw
    keys = sorted(raw)
    mags = [abs(raw[k]["score"]) for k in keys]
    strong = 0.25 * float(np.median(mags)) if mags else 0.0
    out = {}
    for i, k in enumerate(keys):
        r = dict(raw[k])
        r["sure"] = abs(r["score"]) >= strong and r.get("n", 0) >= 2
        if not r["sure"]:
            nb = [raw[keys[j]] for j in range(max(0, i - 2), min(len(keys), i + 3)) if j != i
                  and abs(raw[keys[j]]["score"]) >= strong]
            if nb:
                tot = sum(x["score"] for x in nb)
                r["side"] = "near" if tot > 0 else "far"
        out[k] = r
    return out
