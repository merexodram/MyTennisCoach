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


def save_calibration(path: Path, points: dict, size: tuple[int, int]) -> None:
    data = {"size": list(size), "points": {str(k): [float(v[0]), float(v[1])] for k, v in points.items()}}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_calibration(path: Path, width: int, height: int):
    """Read clicked points and return (H, error_px) for a video of the given size."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sx, sy = width / data["size"][0], height / data["size"][1]
    points = {}
    for k, (x, y) in data["points"].items():
        points[k if k == NET_CENTRE else int(k)] = (x * sx, y * sy)
    return fit_points(points)
