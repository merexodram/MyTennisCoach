"""Ball tracking with TrackNet, plus track cleaning."""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np
import torch

from . import upstream

NET_W, NET_H = 640, 360


class BallTracker:
    """TrackNet wrapper. Frames must be fed in order; call reset() after a jump."""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self.model = upstream.ball_net()
        self.model.load_state_dict(torch.load(upstream.weights("tracknet_ball.pt"), map_location=device))
        self.model.to(device).eval()
        # Half precision is about twice as fast on a GPU, but on some cards it
        # overflows and the network sees nothing. It is switched on only after
        # it has reproduced the full-precision result on real frames.
        self.half_state = "untested" if device.startswith("cuda") else "off"
        self.model_half = None
        self.buf: deque[np.ndarray] = deque(maxlen=2)

    def reset(self) -> None:
        self.buf.clear()

    @torch.no_grad()
    def infer(self, frames: list[np.ndarray]) -> list:
        """Ball candidates for a run of consecutive frames, in one batch.

        Each result is a list of up to 4 blobs (x, y, score), strongest first,
        or None. The first two frames after a reset have no history and give None.
        """
        if not frames:
            return []
        h, w = frames[0].shape[:2]
        stacks, slots = [], []
        for k, frame in enumerate(frames):
            small = cv2.resize(frame, (NET_W, NET_H))
            if len(self.buf) == 2:
                stacks.append(np.concatenate((small, self.buf[1], self.buf[0]), axis=2))
                slots.append(k)
            self.buf.append(small)
        out: list = [None] * len(frames)
        if not stacks:
            return out
        inp = torch.from_numpy(np.stack(stacks).transpose(0, 3, 1, 2)).to(self.device)
        if self.half_state == "on":
            heat_all = self._heat(self.model_half, inp.half())
        else:
            heat_all = self._heat(self.model, inp.float())
            if self.half_state == "untested" and (heat_all > 127).any():
                self._test_half(inp, heat_all)
        for k, heat in zip(slots, heat_all):
            out[k] = self._blobs(heat, w, h)
        return out

    @staticmethod
    def _heat(model, inp: torch.Tensor) -> np.ndarray:
        return model(inp / 255.0).argmax(dim=1).reshape(-1, NET_H, NET_W).to(torch.uint8).cpu().numpy()

    def _test_half(self, inp: torch.Tensor, reference: np.ndarray) -> None:
        """Enable half precision only if it finds the same ball pixels."""
        import copy

        try:
            candidate = copy.deepcopy(self.model).half()
            got = self._heat(candidate, inp.half())
            a, b = reference > 127, got > 127
            agree = (a & b).sum() / max(1, (a | b).sum())
        except Exception:
            agree = 0.0
        if agree > 0.8:
            self.model_half, self.half_state = candidate, "on"
        else:
            self.half_state = "off"
        print(f"  ball network half precision: {self.half_state} (agreement {agree:.2f})")

    @staticmethod
    def _blobs(heat: np.ndarray, w: int, h: int):
        mask = (heat > 127).astype(np.uint8)
        if not mask.any():
            return None
        n, labels, _, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
        blobs = []
        for i in range(1, n):
            score = float(heat[labels == i].sum())
            blobs.append((float(cents[i][0]) * w / NET_W, float(cents[i][1]) * h / NET_H, score))
        blobs.sort(key=lambda t: -t[2])
        return blobs[:4] or None

    def step(self, frame: np.ndarray):
        return self.infer([frame])[0]


def _as_candidates(track: list) -> list[list]:
    """Accept both formats: a list of blobs per frame, or one (x, y) per frame."""
    out = []
    for item in track:
        if item is None:
            out.append([])
        elif isinstance(item, tuple):
            out.append([(item[0], item[1], 1.0)])
        else:
            out.append(list(item))
    return out


def resolve(track: list, max_jump_px: float, static_px: float = 12.0) -> list:
    """Pick one ball position per frame from the candidates.

    1. Drop spots that stay put for a long time (a logo, a line mark, a ball
       in someone's hand): a ball in play does not sit still.
    2. Follow the candidate that best continues the current path.
    """
    cands = _as_candidates(track)
    n = len(cands)
    pts = [np.array([(c[0], c[1]) for c in cs], dtype=np.float64).reshape(-1, 2) for cs in cands]
    keep = []
    for f in range(n):
        kept = []
        for c in cands[f]:
            hits = 0
            for g in list(range(max(0, f - 45), f - 5)) + list(range(f + 6, min(n, f + 46))):
                if len(pts[g]) and np.min(np.hypot(pts[g][:, 0] - c[0], pts[g][:, 1] - c[1])) < static_px:
                    hits += 1
                    if hits >= 4:
                        break
            if hits < 4:
                kept.append(c)
        keep.append(kept)

    out: list = [None] * n
    last, last_f, vel = None, -10**9, np.zeros(2)
    for f in range(n):
        if not keep[f]:
            continue
        dt = f - last_f
        if last is not None and dt <= 8:
            pred = last + vel * dt
            best = min(keep[f], key=lambda c: np.hypot(c[0] - pred[0], c[1] - pred[1]))
            if np.hypot(best[0] - last[0], best[1] - last[1]) > max_jump_px * (1 + 0.5 * (dt - 1)):
                best = keep[f][0]                      # path lost: restart from the strongest blob
                vel = np.zeros(2)
            else:
                vel = (np.array(best[:2]) - last) / dt
        else:
            best, vel = keep[f][0], np.zeros(2)
        out[f] = (best[0], best[1])
        last, last_f = np.array(best[:2]), f
    return out


def clean_track(track: list, max_jump_px: float, max_gap: int = 6) -> np.ndarray:
    """Remove isolated jumps and fill short gaps. Returns (N, 2) with NaN where unknown."""
    track = resolve(track, max_jump_px)
    xy = np.array([p if p is not None else (np.nan, np.nan) for p in track], dtype=np.float64)
    n = len(xy)
    # A point that is far from both neighbours is an outlier.
    for i in range(n):
        if np.isnan(xy[i, 0]):
            continue
        prev = next((xy[j] for j in range(i - 1, max(i - 4, -1), -1) if not np.isnan(xy[j, 0])), None)
        nxt = next((xy[j] for j in range(i + 1, min(i + 4, n)) if not np.isnan(xy[j, 0])), None)
        far_prev = prev is None or np.linalg.norm(xy[i] - prev) > max_jump_px
        far_next = nxt is None or np.linalg.norm(xy[i] - nxt) > max_jump_px
        if far_prev and far_next:
            xy[i] = np.nan
    # Linear interpolation across short gaps only.
    valid = np.flatnonzero(~np.isnan(xy[:, 0]))
    for a, b in zip(valid[:-1], valid[1:]):
        gap = b - a - 1
        if 0 < gap <= max_gap and np.linalg.norm(xy[b] - xy[a]) <= max_jump_px * (gap + 1) / 2:
            for k in range(1, gap + 1):
                xy[a + k] = xy[a] + (xy[b] - xy[a]) * k / (gap + 1)
    return xy
