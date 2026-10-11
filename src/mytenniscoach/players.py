"""Player detection and selection.

YOLO finds every person in frame (players, officials, ball kids, crowd).
The two players are the people standing on or just behind the court, one in
each half, chosen by where their feet land in court coordinates and by how much
they move.
"""
from __future__ import annotations

import numpy as np

from . import court

BEHIND_BASELINE_M = 9.0     # how far behind the baseline a player may stand
BESIDE_COURT_M = 4.0        # how far outside the doubles line
NET_ZONE_M = 4.0            # beside the net: umpire chair and ball kids, never players


class PlayerFinder:
    def __init__(self, device: str = "cpu", weights: str | None = None, imgsz: int = 960):
        from ultralytics import YOLO

        from . import upstream

        # ultralytics downloads the file on first use; keep it with the other weights.
        self.model = YOLO(weights or str(upstream.MODELS / "yolov8s.pt"))
        self.device = device
        self.imgsz = imgsz
        self.batch = 2

    def people_batch(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        """For each frame, an (N, 5) array: x1, y1, x2, y2, confidence per person."""
        if not frames:
            return []
        import torch

        results, k = [], 0
        while k < len(frames):                             # small batches: the GPU is shared with two other networks
            try:
                results += self.model.predict(frames[k: k + self.batch], classes=[0], conf=0.25, imgsz=self.imgsz,
                                              device=self.device, verbose=False)
                k += self.batch
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache()
                if self.batch == 1:
                    raise
                self.batch = max(1, self.batch // 2)
                print(f"  GPU memory full: player network batch reduced to {self.batch}")
        out = []
        for res in results:
            if res.boxes is None or len(res.boxes) == 0:
                out.append(np.zeros((0, 5), dtype=np.float32))
            else:
                out.append(np.hstack([res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy()[:, None]]))
        return out

    def people(self, frame: np.ndarray) -> np.ndarray:
        return self.people_batch([frame])[0]


def feet(box: np.ndarray) -> tuple[float, float]:
    return (float(box[0] + box[2]) / 2.0, float(box[3]))


def _candidates(boxes: np.ndarray, H: np.ndarray, sign: float):
    """People whose feet are in one half of the court or its run-off area."""
    if len(boxes) == 0:
        return []
    pos = court.to_court(H, [feet(b) for b in boxes])
    out = []
    for b, (x, y) in zip(boxes, pos):
        ys = y * sign                                   # distance from the net into this half
        if ys < 0.3 or ys > court.HALF_LENGTH + BEHIND_BASELINE_M:
            continue
        if abs(x) > court.HALF_DOUBLES + BESIDE_COURT_M:
            continue
        if ys < NET_ZONE_M and abs(x) > court.HALF_SINGLES + 0.5:
            continue                                    # umpire chair, ball kids at the net posts
        out.append((b, (float(x), float(y))))
    return out


def _tracklets(cands_per_frame: list, max_step_m: float, max_gap: int) -> list[dict]:
    """Greedy nearest-neighbour linking of candidates in court coordinates."""
    tracks: list[dict] = []
    for f, cands in enumerate(cands_per_frame):
        used = set()
        for b, xy in cands:
            best, best_d = None, max_step_m
            for k, t in enumerate(tracks):
                if k in used or f - t["last_f"] > max_gap:
                    continue
                d = float(np.hypot(xy[0] - t["xy"][0], xy[1] - t["xy"][1]))
                if d < best_d:
                    best, best_d = k, d
            if best is None:
                tracks.append({"xy": xy, "last_f": f, "pts": {f: (b, xy)}})
                used.add(len(tracks) - 1)
            else:
                t = tracks[best]
                t["xy"], t["last_f"] = xy, f
                t["pts"][f] = (b, xy)
                used.add(best)
    return tracks


def _score(track: dict, sign: float) -> float:
    """Players move around; officials and ball kids mostly stand still."""
    xy = np.array([p[1] for p in track["pts"].values()])
    if len(xy) < 8:
        return -1.0
    k = 7                                               # median filter against jitter
    sm = np.array([np.median(xy[max(0, i - k // 2): i + k // 2 + 1], axis=0) for i in range(len(xy))])
    extent = float(np.ptp(sm[:, 0]) + np.ptp(sm[:, 1]))
    mean_x, mean_ys = float(np.mean(sm[:, 0])), float(np.mean(sm[:, 1]) * sign)
    # Small preference for someone positioned like a player.
    central = 1.0 if abs(mean_x) < court.HALF_DOUBLES + 1.0 and mean_ys < court.HALF_LENGTH + 4.5 else 0.0
    return extent + central + 0.002 * len(xy)


def select(boxes_per_frame: list, Hs: list) -> list[dict]:
    """Choose the near and far player for every frame.

    Works on the whole video at once: within each stretch of continuous court
    view, the player in each half is the tracked person who moves the most.
    Returns one dict per frame: {'near': (box, xy_m) | None, 'far': ...}.
    """
    n = len(Hs)
    chosen = [{"near": None, "far": None} for _ in range(n)]
    # Stretches of continuous court view.
    start = None
    stretches = []
    for i in range(n + 1):
        ok = i < n and Hs[i] is not None
        if ok and start is None:
            start = i
        if not ok and start is not None:
            stretches.append((start, i))
            start = None
    for a, b in stretches:
        for side, sign, step in (("near", 1.0, 1.5), ("far", -1.0, 2.5)):
            cands = [_candidates(boxes_per_frame[f], Hs[f], sign) for f in range(a, b)]
            tracks = _tracklets(cands, max_step_m=step, max_gap=12)
            scored = sorted(((_score(t, sign), t) for t in tracks), key=lambda st: -st[0])
            for score, t in scored:                      # strongest mover first; others fill gaps
                if score < MIN_SCORE:
                    break
                taken = sum(chosen[a + f][side] is not None for f in t["pts"])
                if taken > 0.2 * len(t["pts"]):
                    continue                                # mostly overlaps someone already chosen
                if not _continues(chosen, side, t, a):
                    continue
                for f, item in t["pts"].items():
                    if chosen[a + f][side] is None:
                        chosen[a + f][side] = item
    return chosen


MIN_SCORE = 0.9             # below this a track is a bystander


def _continues(chosen, side, track, offset, reach=40, max_m=4.0) -> bool:
    """A gap-filling track must join up with what is already chosen around it."""
    fs = sorted(track["pts"])
    for f_edge, direction in ((fs[0], -1), (fs[-1], 1)):
        for d in range(1, reach + 1):
            g = offset + f_edge + direction * d
            if 0 <= g < len(chosen) and chosen[g][side] is not None:
                ref, me = chosen[g][side][1], track["pts"][f_edge][1]
                if np.hypot(me[0] - ref[0], me[1] - ref[1]) > max_m:
                    return False
                break
    return True
