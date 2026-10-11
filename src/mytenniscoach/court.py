"""Court geometry and court keypoint detection.

Court coordinates are metres, origin at the centre of the net,
x to the right as seen by the camera, y positive towards the camera
(near baseline at y = +11.885).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import torch

from . import upstream

HALF_LENGTH = 11.885      # net to baseline
HALF_DOUBLES = 5.485
HALF_SINGLES = 4.115
SERVICE = 6.40            # net to service line

# The 14 keypoints, in the order the TennisCourtDetector model outputs them.
KEYPOINTS_M = np.array([
    (-HALF_DOUBLES, -HALF_LENGTH), (HALF_DOUBLES, -HALF_LENGTH),   # 0,1  far baseline
    (-HALF_DOUBLES, HALF_LENGTH), (HALF_DOUBLES, HALF_LENGTH),     # 2,3  near baseline
    (-HALF_SINGLES, -HALF_LENGTH), (-HALF_SINGLES, HALF_LENGTH),   # 4,5  left singles line
    (HALF_SINGLES, -HALF_LENGTH), (HALF_SINGLES, HALF_LENGTH),     # 6,7  right singles line
    (-HALF_SINGLES, -SERVICE), (HALF_SINGLES, -SERVICE),           # 8,9  far service line
    (-HALF_SINGLES, SERVICE), (HALF_SINGLES, SERVICE),             # 10,11 near service line
    (0.0, -SERVICE), (0.0, SERVICE),                               # 12,13 centre service line
], dtype=np.float32)

# Line segments (keypoint index pairs) for drawing.
LINES = [(0, 1), (2, 3), (0, 2), (1, 3), (4, 5), (6, 7), (8, 9), (10, 11), (12, 13)]

NET_W, NET_H = 640, 360


class CourtDetector:
    def __init__(self, device: str = "cpu"):
        self.device = device
        self.model = upstream.court_net()
        self.model.load_state_dict(torch.load(upstream.weights("court_detector.pt"), map_location=device))
        self.model.to(device).eval()               # full precision: it only runs a few times a second

    @torch.no_grad()
    def keypoints(self, frame: np.ndarray) -> np.ndarray:
        """Return a (14, 2) array of image points; rows are NaN where not found."""
        h, w = frame.shape[:2]
        img = cv2.resize(frame, (NET_W, NET_H)).astype(np.float32) / 255.0
        inp = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        heat = torch.sigmoid(self.model(inp)[0]).cpu().numpy()
        pts = np.full((14, 2), np.nan, dtype=np.float32)
        for k in range(14):
            hm = heat[k]
            peak = float(hm.max())
            if peak < 0.5:
                continue
            ys, xs = np.nonzero(hm > 0.5 * peak)
            wts = hm[ys, xs]
            pts[k] = (
                float((xs * wts).sum() / wts.sum()) * w / NET_W,
                float((ys * wts).sum() / wts.sum()) * h / NET_H,
            )
        return pts


def fit_homography(kps: np.ndarray, tol_px: float = 6.0):
    """Homography image -> court metres from detected keypoints.

    Returns (H, n_inliers, reprojection_error_px) or (None, 0, inf).
    """
    ok = ~np.isnan(kps[:, 0])
    if ok.sum() < 6:
        return None, 0, float("inf")
    H_c2i, mask = cv2.findHomography(KEYPOINTS_M[ok], kps[ok], cv2.RANSAC, tol_px)
    if H_c2i is None:
        return None, 0, float("inf")
    proj = cv2.perspectiveTransform(KEYPOINTS_M[ok].reshape(-1, 1, 2), H_c2i).reshape(-1, 2)
    err = np.linalg.norm(proj - kps[ok], axis=1)
    inl = mask.ravel().astype(bool)
    if inl.sum() < 6:
        return None, int(inl.sum()), float("inf")
    return np.linalg.inv(H_c2i), int(inl.sum()), float(err[inl].mean())


def to_court(H: np.ndarray, pts_px) -> np.ndarray:
    pts = np.asarray(pts_px, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, H).reshape(-1, 2)


def to_image(H: np.ndarray, pts_m) -> np.ndarray:
    pts = np.asarray(pts_m, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, np.linalg.inv(H)).reshape(-1, 2)


# ---------------------------------------------------------------------------
# Manual calibration for a fixed camera
#
# The keypoint network was trained on broadcast footage shot from high up. From
# a low camera on a club court it often finds nothing. A camera that does not
# move needs the court located only once, so a handful of clicked points does
# the job, and more reliably.

NET_CENTRE = "net"                    # extra point: where the net's centre strap meets the ground
POINT_NAMES = {
    0: "far baseline, left doubles corner", 1: "far baseline, right doubles corner",
    2: "near baseline, left doubles corner", 3: "near baseline, right doubles corner",
    4: "far baseline, left singles line", 5: "near baseline, left singles line",
    6: "far baseline, right singles line", 7: "near baseline, right singles line",
    8: "far service line, left end", 9: "far service line, right end",
    10: "near service line, left end", 11: "near service line, right end",
    12: "far service line, centre (T)", 13: "near service line, centre (T)",
    NET_CENTRE: "net centre, on the ground",
}


def _court_xy(key) -> tuple[float, float]:
    if key == NET_CENTRE:
        return (0.0, 0.0)
    return tuple(float(v) for v in KEYPOINTS_M[int(key)])


def fit_points(points: dict) -> tuple[np.ndarray | None, float]:
    """Homography image -> court metres from {keypoint: (x, y) in pixels}.

    Returns (H, worst reprojection error in pixels); (None, inf) with fewer than 4 points.
    """
    if len(points) < 4:
        return None, float("inf")
    crt = np.float32([_court_xy(k) for k in points])
    img = np.float32([points[k] for k in points])
    H_c2i, _ = cv2.findHomography(crt, img, 0)
    if H_c2i is None:
        return None, float("inf")
    proj = cv2.perspectiveTransform(crt.reshape(-1, 1, 2), H_c2i).reshape(-1, 2)
    return np.linalg.inv(H_c2i), float(np.linalg.norm(proj - img, axis=1).max())


def calibration_file(video_path: Path) -> Path:
    return video_path.with_name(video_path.stem + ".court.json")


def find_calibration(video_path: Path) -> Path | None:
    """The court file for a video: next to it, or with the same name in data/raw or outputs/cache."""
    name = video_path.stem + ".court.json"
    root = Path(__file__).resolve().parents[2]
    for folder in (video_path.parent, root / "data" / "raw", root / "outputs" / "cache", root):
        if (folder / name).exists():
            return folder / name
    return None


def save_calibration(path: Path, points: dict, size: tuple[int, int], me: dict | None = None) -> None:
    data = {"size": list(size), "points": {str(k): [float(v[0]), float(v[1])] for k, v in points.items()}}
    if me is not None:
        data["me"] = me                              # {"frame": index in the clicked video, "fps": ..., "point": [x, y]}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_me(path: Path, width: int, height: int, fps: float):
    """The click on "me": (frame index, (x, y)) for a video of the given size and frame rate, or None."""
    data = json.loads(path.read_text(encoding="utf-8"))
    me = data.get("me")
    if not me:
        return None
    sx, sy = width / data["size"][0], height / data["size"][1]
    frame = int(round(me["frame"] * fps / me.get("fps", fps)))
    return frame, (me["point"][0] * sx, me["point"][1] * sy)


def load_calibration(path: Path, width: int, height: int):
    """Read clicked points and return (H, error_px) for a video of the given size."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sx, sy = width / data["size"][0], height / data["size"][1]
    points = {}
    for k, (x, y) in data["points"].items():
        points[k if k == NET_CENTRE else int(k)] = (x * sx, y * sy)
    return fit_points(points)


def far_zoom_rect(H: np.ndarray, width: int, height: int, min_w: int = 640):
    """Image rectangle (x, y, w, h, 16:9) around the far half of the court, or None.

    From a low camera the far half covers only a thin strip of the picture, and
    the ball network, which sees the whole frame shrunk to 640x360, loses the
    ball there. Looking at that strip a second time, enlarged, recovers it.
    Returns None when the far half is already large enough (a high camera).
    """
    m = HALF_DOUBLES + 2.5
    pts = to_image(H, [(-m, 0.0), (m, 0.0), (-m, -(HALF_LENGTH + 4.0)), (m, -(HALF_LENGTH + 4.0))])
    net_y = float(to_image(H, [(0.0, 0.0)])[0][1])
    base_y = float(to_image(H, [(0.0, -HALF_LENGTH)])[0][1])
    if abs(net_y - base_y) > 0.2 * height:
        return None
    x0, x1 = float(pts[:, 0].min()), float(pts[:, 0].max())
    y0, y1 = float(pts[:, 1].min()), float(pts[:, 1].max())
    strip = y1 - y0
    y0 -= 2.5 * strip                                  # air above the far court: lobs, serves, the toss
    y1 += 0.3 * strip
    w = max(float(min_w), x1 - x0, (y1 - y0) * 16 / 9)
    w = min(w, float(width))
    h = w * 9 / 16
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx = int(round(min(max(cx - w / 2, 0), width - w)))
    ry = int(round(min(max(cy - h / 2, 0), height - h)))
    return rx, ry, int(round(w)), int(round(h))


def snap_to_lines(frame: np.ndarray, point, radius: int | None = None):
    """Move a clicked court point onto the real crossing of the two painted lines near it.

    A click is a few pixels off, more so on a scaled-down picture, and a few
    pixels at the far end of the court are metres. The lines themselves are
    in the picture, so use them: find the two lines around the click and
    return where they cross. Returns the click unchanged if no clear crossing
    is found within reach.
    """
    h, w = frame.shape[:2]
    r = radius or max(18, int(round(w / 1920 * 30)))
    x, y = int(round(point[0])), int(round(point[1]))
    x0, y0, x1, y1 = max(0, x - r), max(0, y - r), min(w, x + r + 1), min(h, y + r + 1)
    if x1 - x0 < 12 or y1 - y0 < 12:
        return (float(point[0]), float(point[1])), False
    gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    # Lines are thin and brighter than the court around them.
    k = max(5, (r // 3) | 1)
    top = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    _, mask = cv2.threshold(top, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if mask.mean() < 2 or mask.mean() > 120:
        return (float(point[0]), float(point[1])), False
    lines = cv2.HoughLines(mask, 1, np.pi / 180, max(8, int(0.5 * r)))
    if lines is None:
        return (float(point[0]), float(point[1])), False
    picked: list = []
    for rho, theta in lines[:, 0, :]:
        if all(min(abs(theta - t), np.pi - abs(theta - t)) > np.radians(12) for _, t in picked):
            picked.append((rho, theta))
        if len(picked) == 2:
            break
    if len(picked) < 2:
        return (float(point[0]), float(point[1])), False
    ys, xs = np.nonzero(mask)
    fitted = []
    for rho, theta in picked:                       # refit each line through the middle of its paint
        d = np.abs(xs * np.cos(theta) + ys * np.sin(theta) - rho)
        sel = d < 3.0
        if sel.sum() < 6:
            return (float(point[0]), float(point[1])), False
        vx, vy, px, py = cv2.fitLine(np.column_stack([xs[sel], ys[sel]]).astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        fitted.append((vx, vy, px, py))
    (a1, b1, p1, q1), (a2, b2, p2, q2) = fitted
    det = a1 * b2 - b1 * a2
    if abs(det) < 1e-6:
        return (float(point[0]), float(point[1])), False
    t = ((p2 - p1) * b2 - (q2 - q1) * a2) / det
    cx, cy = p1 + t * a1 + x0, q1 + t * b1 + y0
    if np.hypot(cx - point[0], cy - point[1]) > 0.8 * r:
        return (float(point[0]), float(point[1])), False
    return (float(cx), float(cy)), True


def point_errors(points: dict) -> dict:
    """How far each clicked point lies from the fitted court, in pixels."""
    H, _ = fit_points(points)
    if H is None:
        return {}
    return {k: float(np.linalg.norm(to_image(H, [_court_xy(k)])[0] - np.float32(points[k]))) for k in points}
