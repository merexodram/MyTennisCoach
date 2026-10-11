"""Technique measurements for one player ("me"), stroke by stroke.

Around every stroke the player is cut out of the ORIGINAL recording (full
resolution, so a small far-side player still has pixels), a pose network finds
17 body points per frame, and a handful of measurements are derived.

What a single camera behind the court can and cannot see:
  * heights, reach to the side, knee and elbow angles as they appear in the
    picture, where the feet are on the court: measured;
  * rotation of shoulders and hips: only estimated, from how narrow they look;
  * anything along the camera's line of sight (how far in front of the body
    the ball is met): not measurable from this view.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import court, upstream, video

NOSE, L_SH, R_SH, L_EL, R_EL, L_WR, R_WR, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANK, R_ANK = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
SKELETON = [(L_SH, R_SH), (L_SH, L_EL), (L_EL, L_WR), (R_SH, R_EL), (R_EL, R_WR), (L_SH, L_HIP), (R_SH, R_HIP),
            (L_HIP, R_HIP), (L_HIP, L_KNEE), (L_KNEE, L_ANK), (R_HIP, R_KNEE), (R_KNEE, R_ANK)]
MIN_CONF = 0.35
BEFORE_S, AFTER_S = 0.8, 0.4            # window around contact


@dataclass
class StrokeTechnique:
    frame: int                                   # contact frame (working-copy numbering)
    stroke: str = "unknown"                      # serve | forehand | backhand | volley-less first guess
    contact_height_m: float | None = None
    contact_reach_m: float | None = None         # sideways distance of the hitting hand from the hips
    knee_flex_deg: float | None = None           # smallest knee angle in the 0.5 s before contact (180 = straight)
    elbow_angle_deg: float | None = None         # hitting arm at contact
    trunk_tilt_deg: float | None = None          # lean of the trunk from vertical at contact
    shoulder_turn_deg: float | None = None       # estimate: biggest turn of the shoulders during the backswing
    hip_shoulder_sep_deg: float | None = None    # estimate: shoulders turned further than hips
    stance: str | None = None
    swing_duration_s: float | None = None
    off_hand_on_racket: bool | None = None       # at contact: two-handed, or the other hand still on the racket
    pose_frames: int = 0                         # frames in the window with a usable pose
    keypoints: dict = field(default_factory=dict)  # frame -> (17, 3) array, working-copy coordinates


class PoseEstimator:
    def __init__(self, device: str = "cpu", weights: str | None = None, imgsz: int = 384):
        from ultralytics import YOLO

        self.model = YOLO(weights or str(upstream.MODELS / "yolov8s-pose.pt"))
        self.device, self.imgsz = device, imgsz

    def poses(self, crops: list[np.ndarray]) -> list[np.ndarray | None]:
        """For each crop, the (17, 3) keypoints (x, y, confidence) of its main person, or None."""
        out: list = []
        for k in range(0, len(crops), 8):
            for res in self.model.predict(crops[k: k + 8], imgsz=self.imgsz, device=self.device, verbose=False):
                if res.keypoints is None or len(res.keypoints) == 0:
                    out.append(None)
                    continue
                kp = res.keypoints.data.cpu().numpy()                   # (people, 17, 3)
                h, w = res.orig_shape
                # Main person: the one whose body centre is nearest the middle of the crop.
                centre = np.array([w / 2, h / 2])
                best = min(range(len(kp)), key=lambda i: np.linalg.norm(kp[i][[L_HIP, R_HIP, L_SH, R_SH], :2].mean(0) - centre))
                out.append(kp[best])
        return out


def _pt(kp, i):
    return kp[i, :2] if kp is not None and kp[i, 2] >= MIN_CONF else None


def _mid(kp, i, j):
    a, b = _pt(kp, i), _pt(kp, j)
    return (a + b) / 2 if a is not None and b is not None else None


def _angle(a, b, c) -> float | None:
    if a is None or b is None or c is None:
        return None
    v1, v2 = a - b, c - b
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / n, -1, 1)))) if n > 1e-6 else None


def _body_px(kps: list) -> float | None:
    """Standing body height in pixels: the tallest nose-to-ankle span seen, plus the top of the head."""
    spans = []
    for kp in kps:
        nose, ank = _pt(kp, NOSE), _mid(kp, L_ANK, R_ANK)
        if nose is not None and ank is not None:
            spans.append(ank[1] - nose[1])
    return float(np.percentile(spans, 90)) / 0.93 if len(spans) >= 3 else None      # nose is at about 93 % of height


def measure(frames: list[int], kps: list, contact: int, side: str, hand: str, H, fps: float,
            height_m: float, first_in_rally: bool) -> StrokeTechnique:
    """Turn the poses of one stroke window into measurements."""
    t = StrokeTechnique(frame=contact)
    good = {f: kp for f, kp in zip(frames, kps) if kp is not None}
    t.pose_frames = len(good)
    t.keypoints = good
    if len(good) < 5:
        return t
    at = min(good, key=lambda f: abs(f - contact))
    kp = good[at]
    body = _body_px(list(good.values()))
    m_per_px = height_m / body if body else None

    wr_i, el_i, sh_i = (R_WR, R_EL, R_SH) if hand == "right" else (L_WR, L_EL, L_SH)
    off_wr = L_WR if hand == "right" else R_WR
    wrist, hips, shoulders = _pt(kp, wr_i), _mid(kp, L_HIP, R_HIP), _mid(kp, L_SH, R_SH)
    ankles, nose = _mid(kp, L_ANK, R_ANK), _pt(kp, NOSE)

    # Which stroke. The near player has their back to the camera, so their right
    # side is on the right of the picture; the far player faces it, mirrored.
    if wrist is not None and hips is not None:
        view = 1.0 if side == "near" else -1.0
        handed = 1.0 if hand == "right" else -1.0
        sideways = (wrist[0] - hips[0]) * view * handed
        overhead = shoulders is not None and wrist[1] < shoulders[1] - 0.6 * abs(hips[1] - shoulders[1])
        if overhead:
            t.stroke = "serve" if first_in_rally else "smash"
        else:
            t.stroke = "forehand" if sideways > 0 else "backhand"
        if m_per_px:
            t.contact_reach_m = float(abs(wrist[0] - hips[0]) * m_per_px)
            if ankles is not None:
                t.contact_height_m = float((ankles[1] - wrist[1]) * m_per_px)

    t.elbow_angle_deg = _angle(_pt(kp, sh_i), _pt(kp, el_i), wrist)
    if hips is not None and shoulders is not None:
        v = shoulders - hips
        t.trunk_tilt_deg = float(np.degrees(np.arctan2(abs(v[0]), abs(v[1]))))
    off = _pt(kp, off_wr)
    if wrist is not None and off is not None and body:
        t.off_hand_on_racket = bool(np.linalg.norm(wrist - off) < 0.12 * body)

    # Deepest knee bend while loading.
    knees = []
    for f, k in good.items():
        if contact - int(0.5 * fps) <= f <= contact:
            for hip, knee, ank in ((L_HIP, L_KNEE, L_ANK), (R_HIP, R_KNEE, R_ANK)):
                a = _angle(_pt(k, hip), _pt(k, knee), _pt(k, ank))
                if a is not None:
                    knees.append(a)
    if knees:
        t.knee_flex_deg = float(np.percentile(knees, 10))

    # Turn of shoulders and hips, from how narrow they look compared with their widest.
    sh_w, hip_w = {}, {}
    for f, k in good.items():
        a, b = _pt(k, L_SH), _pt(k, R_SH)
        c, d = _pt(k, L_HIP), _pt(k, R_HIP)
        if a is not None and b is not None:
            sh_w[f] = abs(a[0] - b[0])
        if c is not None and d is not None:
            hip_w[f] = abs(c[0] - d[0])
    before = [f for f in sh_w if f <= contact]
    if len(sh_w) >= 5 and before:
        full = max(sh_w.values())
        f_turn = min(before, key=lambda f: sh_w[f])
        t.shoulder_turn_deg = float(np.degrees(np.arccos(np.clip(sh_w[f_turn] / full, 0, 1))))
        if len(hip_w) >= 5 and f_turn in hip_w:
            hip_turn = float(np.degrees(np.arccos(np.clip(hip_w[f_turn] / max(hip_w.values()), 0, 1))))
            t.hip_shoulder_sep_deg = t.shoulder_turn_deg - hip_turn

    # Stance: direction of the line through the feet, on the court, relative to the baseline.
    la, ra = _pt(kp, L_ANK), _pt(kp, R_ANK)
    if H is not None and la is not None and ra is not None:
        fa, fb = court.to_court(H, [la, ra])
        d = fb - fa
        ang = float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))       # 0 = feet along the baseline
        t.stance = "open" if ang < 25 else ("semi_open" if ang < 55 else "closed")

    # Forward swing: from the last moment the hitting hand was almost still to contact.
    track = [(f, _pt(k, wr_i)) for f, k in sorted(good.items()) if f <= contact]
    track = [(f, p) for f, p in track if p is not None]
    if len(track) >= 4 and body:
        speed = [(f2, np.linalg.norm(p2 - p1) / max(1, f2 - f1) / body) for (f1, p1), (f2, p2) in zip(track[:-1], track[1:])]
        start = None
        for f, s in reversed(speed):
            if s < 0.012:                                               # under about 1 % of body height per frame
                start = f
                break
        if start is not None and contact > start:
            t.swing_duration_s = float((contact - start) / fps)
    return t


def analyse_strokes(work_path, original_path, info, chosen: list, shots: list, me_side_by_rally: dict,
                    Hs: list, hand: str, height_m: float, device: str = "cpu", log=print) -> dict:
    """Pose and measurements for every stroke hit by "me". Returns {contact frame: StrokeTechnique}."""
    mine = [s for s in shots if me_side_by_rally.get(s.rally) == s.hitter]
    if not mine:
        return {}
    oinfo = video.probe(original_path)
    scale = oinfo.width / info.width                                    # working copy -> original pixels
    step = oinfo.fps / info.fps
    reader = video.Reader(original_path)
    pose = PoseEstimator(device)
    out: dict = {}
    for n, s in enumerate(mine):
        side = s.hitter
        lo, hi = max(0, s.frame - int(BEFORE_S * info.fps)), min(len(chosen) - 1, s.frame + int(AFTER_S * info.fps))
        frames, crops, offsets = [], [], []
        last_box = None
        for f in range(lo, hi + 1):
            p = chosen[f].get(side)
            box = p[0] if p is not None else last_box
            if box is None:
                continue
            last_box = box
            got = reader.read(int(round(f * step)), 1)
            if not got:
                continue
            x1, y1, x2, y2 = (float(v) * scale for v in box[:4])
            w, h = x2 - x1, y2 - y1
            # Room around the player for the racket arm and a lunge.
            cx1, cy1 = int(max(0, x1 - 0.6 * h)), int(max(0, y1 - 0.35 * h))
            cx2, cy2 = int(min(oinfo.width, x2 + 0.6 * h)), int(min(oinfo.height, y2 + 0.12 * h))
            if cx2 - cx1 < 8 or cy2 - cy1 < 8:
                continue
            frames.append(f)
            crops.append(got[0][cy1:cy2, cx1:cx2])
            offsets.append((cx1, cy1))
        kps = pose.poses(crops)
        mapped = []
        for kp, (ox, oy) in zip(kps, offsets):
            if kp is None:
                mapped.append(None)
                continue
            kp = kp.copy()
            kp[:, 0] = (kp[:, 0] + ox) / scale                          # back to working-copy coordinates
            kp[:, 1] = (kp[:, 1] + oy) / scale
            mapped.append(kp)
        first = s.seq == 1
        out[s.frame] = measure(frames, mapped, s.frame, side, hand, Hs[s.frame], info.fps, height_m, first)
        if (n + 1) % 10 == 0:
            log(f"  technique: {n + 1}/{len(mine)} strokes")
    reader.close()
    return out


def draw(frame: np.ndarray, kp: np.ndarray, color=(255, 255, 0)) -> None:
    for a, b in SKELETON:
        if kp[a, 2] >= MIN_CONF and kp[b, 2] >= MIN_CONF:
            cv2.line(frame, (int(kp[a, 0]), int(kp[a, 1])), (int(kp[b, 0]), int(kp[b, 1])), color, 2, cv2.LINE_AA)
    for i in range(17):
        if kp[i, 2] >= MIN_CONF:
            cv2.circle(frame, (int(kp[i, 0]), int(kp[i, 1])), 3, (0, 0, 255), -1, cv2.LINE_AA)
