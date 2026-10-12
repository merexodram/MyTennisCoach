"""Ball flight in 3D from one camera: speed, net clearance, height, spin.

The court homography gives the camera itself (focal length, position and
orientation) if the lens has no strong distortion. With the camera known, the
flight between a stroke and its bounce is fitted with real ball physics:
gravity, air drag and the Magnus force of the spin. Start point near the
hitter, end point the bounce, the picture in between.

What comes out is an estimate. Read it as a trend from session to session with
the same camera, not as a radar gun:

* speed_kmh: ball speed just after contact
* net_clearance_m: height above the net tape where the ball crosses the net
* apex_m: highest point of the flight
* spin_rpm: positive = topspin, negative = slice/backspin
* bounce_angle_deg: how steeply the ball comes down

Every shot carries the fit error in pixels; poor fits are dropped.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import court

G = 9.81
BALL_R = 0.0335
K_AIR = 1.21 * np.pi * BALL_R ** 2 / (2 * 0.057)     # rho*A / (2m), 1/m
CD = 0.55                                            # drag coefficient of a fuzzy ball
NET_CENTRE, NET_POST = 0.914, 1.07


@dataclass
class Camera:
    K: np.ndarray
    R: np.ndarray
    t: np.ndarray
    reproj_px: float

    def project(self, X: np.ndarray) -> np.ndarray:
        """Court metres (x, y, z up) -> image pixels; X is (n, 3)."""
        c = (self.R @ X.T).T + self.t
        p = (self.K @ c.T).T
        return p[:, :2] / p[:, 2:3]

    def position(self) -> np.ndarray:
        return -self.R.T @ self.t


def camera_from_homography(H_img2court: np.ndarray, width: int, height: int) -> Camera | None:
    """Recover the camera (pinhole, square pixels, no lens distortion) from the
    ground-plane homography. Action cams must be in linear (no fisheye) mode."""
    import cv2

    gx, gy = np.meshgrid(np.linspace(-6.4, 6.4, 9), np.linspace(-court.HALF_LENGTH, court.HALF_LENGTH, 13))
    plane = np.column_stack([gx.ravel(), gy.ravel()])
    img = court.to_image(H_img2court, plane).astype(np.float32)
    # OpenCV's frame for the court plane has z pointing down; ours points up.
    obj = np.column_stack([plane, np.zeros(len(plane))]).astype(np.float32)
    base = (cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_FIX_ASPECT_RATIO | cv2.CALIB_ZERO_TANGENT_DIST
            | cv2.CALIB_FIX_K1 | cv2.CALIB_FIX_K2 | cv2.CALIB_FIX_K3)
    best = None
    for extra in (0, cv2.CALIB_FIX_PRINCIPAL_POINT):
        K0 = np.array([[float(width), 0, width / 2.0], [0, float(width), height / 2.0], [0, 0, 1.0]])
        try:
            err, K, _, rv, tv = cv2.calibrateCamera([obj], [img], (width, height), K0, np.zeros(5), flags=base | extra)
        except cv2.error:
            continue
        pp_ok = abs(K[0, 2] - width / 2) < 0.15 * width and abs(K[1, 2] - height / 2) < 0.15 * height
        if not pp_ok or not (0.25 * width < K[0, 0] < 8.0 * width):
            continue
        if best is None or err < best[0]:
            best = (err, K, rv[0], tv[0])
    if best is None:
        return None
    err, K, rv, tv = best
    R, _ = cv2.Rodrigues(rv)
    R = R @ np.diag([1.0, 1.0, -1.0])             # z up
    cam = Camera(K, R, tv.ravel(), float(err))
    if cam.position()[2] <= 0.3:
        return None
    return cam


def _simulate(p0, v0, spin, tmax: float, dt: float = 0.008):
    """Integrate a batch of flights. p0, v0: (B, 3); spin: (B,) Magnus lift
    coefficient (positive = topspin, pushes the ball down).
    Returns times (n,) and positions (n, B, 3)."""
    p = np.array(p0, float).reshape(-1, 3)
    v = np.array(v0, float).reshape(-1, 3)
    spin = np.asarray(spin, float).reshape(-1, 1)
    n = max(8, int(np.ceil(tmax / dt)))
    dt = tmax / n
    gvec = np.array([0.0, 0.0, -G])

    def acc(vel):
        speed = np.linalg.norm(vel, axis=1, keepdims=True) + 1e-9
        vh = vel.copy()
        vh[:, 2] = 0.0
        nh = np.linalg.norm(vh, axis=1, keepdims=True) + 1e-9
        axis = np.stack([-vh[:, 1], vh[:, 0], np.zeros(len(vh))], axis=1) / nh   # z x v_h: topspin axis
        lift = np.cross(axis, vel / speed)                                          # down for topspin
        return gvec - K_AIR * CD * speed * vel + K_AIR * spin * speed ** 2 * lift

    out = np.empty((n + 1,) + p.shape)
    out[0] = p
    for i in range(n):
        vm = v + 0.5 * dt * acc(v)
        p = p + dt * vm
        v = v + dt * acc(vm)
        out[i + 1] = p
    return np.linspace(0.0, tmax, n + 1), out


def _at(times, path_t, path):
    """Positions of a batch at given times (k,) -> (k, B, 3)."""
    idx = np.clip(np.searchsorted(path_t, times) - 1, 0, len(path_t) - 2)
    w = ((times - path_t[idx]) / (path_t[idx + 1] - path_t[idx]))[:, None, None]
    return path[idx] * (1 - w) + path[idx + 1] * w


@dataclass
class Flight:
    speed_kmh: float
    net_clearance_m: float | None
    apex_m: float
    spin_rpm: float
    bounce_angle_deg: float
    hit_height_m: float
    fit_px: float


def fit_shot(cam: Camera, ball_px: np.ndarray, f_hit: int, f_bounce: int, bounce_xy: tuple,
             contact_xy: tuple | None, fps: float, serve: bool, px_scale: float) -> Flight | None:
    from scipy.optimize import least_squares

    frames = np.arange(f_hit + 1, f_bounce)
    ok = np.isfinite(ball_px[frames, 0])
    frames = frames[ok]
    if len(frames) < 5 or contact_xy is None:
        return None
    obs = ball_px[frames]
    t_obs = (frames - f_hit) / fps
    T = (f_bounce - f_hit) / fps
    bx, by = bounce_xy
    cx, cy = contact_xy
    z_guess = 2.55 if serve else 1.0
    vx, vy = (bx - cx) / T, (by - cy) / T
    vz = (0.5 * G * T * T - z_guess) / T
    x0 = np.array([cx, cy, z_guess, vx, vy, vz, 0.15 if not serve else 0.05, T])
    sig_px = 2.5 * px_scale

    tmax = T + 4 / fps

    def resid_batch(Q):
        _, B = Q.shape[1], Q.shape[0]
        path_t, path = _simulate(Q[:, :3], Q[:, 3:6], Q[:, 6], tmax)
        pos = _at(t_obs, path_t, path)                         # (k, B, 3)
        ends = np.stack([_at(np.array([Q[b, 7]]), path_t, path[:, b:b + 1])[0, 0] for b in range(B)])
        out = []
        for b in range(B):
            r_img = ((cam.project(pos[:, b]) - obs) / sig_px).ravel()
            e = ends[b]
            r_bounce = np.array([(e[0] - bx) / 0.25, (e[1] - by) / 0.4, e[2] / 0.03])
            q = Q[b]
            r_prior = np.array([(q[0] - cx) / 1.0, (q[1] - cy) / 1.0, (q[2] - z_guess) / (0.25 if serve else 0.5),
                                q[6] / 0.6, (q[7] - T) / (1.5 / fps)])
            out.append(np.concatenate([r_img, r_bounce, r_prior]))
        return np.array(out)

    steps = np.array([0.02, 0.02, 0.01, 0.05, 0.05, 0.05, 0.005, 0.2 / fps])

    def resid(q):
        return resid_batch(q[None])[0]

    def jac(q):
        Q = np.vstack([q, q + np.diag(steps)])
        r = resid_batch(Q)
        return ((r[1:] - r[0]) / steps[:, None]).T

    lo = [cx - 3, cy - 3, 0.1, -80, -80, -40, -0.6, T - 3 / fps]
    hi = [cx + 3, cy + 3, 3.3, 80, 80, 40, 0.6, T + 3 / fps]
    x0 = np.clip(x0, np.array(lo) + 1e-6, np.array(hi) - 1e-6)
    try:
        sol = least_squares(resid, x0, jac=jac, bounds=(lo, hi), x_scale="jac", max_nfev=60)
    except Exception:
        return None
    q = sol.x
    p0, v0, spin, tb = q[:3], q[3:6], q[6], q[7]
    path_t, path = _simulate(p0, v0, [spin], tb)
    path = path[:, 0]
    pos = _at(t_obs[t_obs <= tb], path_t, path[:, None])[:, 0]
    fit = float(np.sqrt(np.mean(np.sum((cam.project(pos) - obs[t_obs <= tb]) ** 2, axis=1))))
    speed = float(np.linalg.norm(v0)) * 3.6
    if fit > 2.5 * sig_px or not (30.0 < speed < 260.0):
        return None
    if p0[2] < 0.15 or p0[2] > 3.25:
        return None                                    # contact height pinned at its limit: fit not trusted
    apex = float(path[:, 2].max())
    clearance = None
    cross = np.nonzero(np.sign(path[:-1, 1]) != np.sign(path[1:, 1]))[0]
    if len(cross):
        i = cross[0]
        w = path[i, 1] / (path[i, 1] - path[i + 1, 1])
        xz = path[i] + w * (path[i + 1] - path[i])
        net_h = NET_CENTRE + (NET_POST - NET_CENTRE) * min(abs(xz[0]) / (court.HALF_DOUBLES + 0.914), 1.0)
        clearance = float(xz[2] - net_h)
        if clearance < -0.05:
            return None                                # a ball that landed in cannot pass through the net
    vb = (path[-1] - path[-2]) / (path_t[1] - path_t[0])
    angle = float(np.degrees(np.arctan2(-vb[2], np.hypot(vb[0], vb[1]))))
    # Magnus lift coefficient -> spin, after Watts & Ferrer: CL = 1 / (2 + v / (r*omega)).
    cl = abs(spin)
    rpm = 0.0
    if cl > 1e-3:
        sp = 1.0 / (1.0 / min(cl, 0.45) - 2.0)
        rpm = float(np.sign(spin) * sp * np.linalg.norm(v0) / BALL_R * 60.0 / (2 * np.pi))
    if abs(rpm) > 5000:
        rpm = float("nan")                             # beyond what amateurs and pros produce: not measured
    return Flight(speed, clearance, apex, rpm, angle, float(p0[2]), fit)


def analyse(shots, ball_px: np.ndarray, Hs: list, fps: float, width: int, height: int) -> int:
    """Fill the flight fields of every shot whose bounce was found. Returns how many."""
    cams: dict = {}
    n = 0
    for s in shots:
        if s.bounce_frame is None or s.bounce_xy_m is None or s.contact_xy_m is None:
            continue
        H = Hs[s.bounce_frame] if s.bounce_frame < len(Hs) else None
        if H is None:
            continue
        key = id(H)
        if key not in cams:
            cams[key] = camera_from_homography(H, width, height)
        cam = cams[key]
        if cam is None or cam.reproj_px > 3.0:
            continue
        try:
            fl = fit_shot(cam, ball_px, s.frame, s.bounce_frame, s.bounce_xy_m, s.contact_xy_m, fps,
                          s.stroke == "serve", height / 480.0)
        except Exception:
            fl = None
        if fl is None:
            continue
        s.flight = fl
        s.speed_kmh = fl.speed_kmh
        n += 1
    return n
