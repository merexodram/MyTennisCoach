"""Process one video: tracks -> events -> database -> annotated video.

    python -m mytenniscoach.process data/raw/clip.mp4
    python -m mytenniscoach.process data/raw/clip.mp4 --far-hand left --no-video

Per-frame tracks are cached in outputs/cache/, so changing the event logic
and re-running takes seconds.
"""
from __future__ import annotations

import argparse
import pickle
import time
from pathlib import Path

import numpy as np

from . import ball, court, db, events, players, render, video

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
CACHE = OUT / "cache"


def pick_device(name: str) -> str:
    if name != "auto":
        return name
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def track(path: Path, device: str, court_every_s: float = 0.2, log=print) -> dict:
    """One streaming pass: court, ball and players for every frame."""
    info = video.probe(path)
    step = max(1, int(round(info.fps * court_every_s)))
    cd, bt, pf = court.CourtDetector(device), ball.BallTracker(device), players.PlayerFinder(device)

    Hs, court_err, raw_ball, boxes = [], [], [], []
    H, err = None, float("inf")
    t0 = time.time()
    for i, frame in video.frames(path):
        if i % step == 0:
            kps = cd.keypoints(frame)
            H, n_inl, err = court.fit_homography(kps)
            if H is not None and (n_inl < 8 or err > 5.0):
                H = None                                   # not the main camera view
        Hs.append(H)
        court_err.append(err)
        # Keep feeding the ball net so its 3-frame buffer stays in order.
        b = bt.step(frame)
        raw_ball.append(b if H is not None else None)
        boxes.append(pf.people(frame) if H is not None else np.zeros((0, 5), np.float32))
        if i and i % 50 == 0:
            log(f"  frame {i}/{info.frames}  {(time.time() - t0) / (i + 1):.2f} s/frame")
    return {"Hs": Hs, "court_err": court_err, "ball": raw_ball, "boxes": boxes}


def analyse(info: video.VideoInfo, tr: dict, hands: dict):
    ball_px = ball.clean_track(tr["ball"], max_jump_px=info.width * 0.12)
    chosen = players.select(tr["boxes"], tr["Hs"])
    shots = events.build_shots(ball_px, chosen, tr["Hs"], info.fps, info.height, hands)
    return ball_px, chosen, shots


def summary(info, tr, ball_px, chosen, shots) -> dict:
    in_view = np.array([H is not None for H in tr["Hs"]])
    n_view = int(in_view.sum())
    raw = np.array([b is not None for b in tr["ball"]])
    return {
        "frames": len(in_view),
        "court_view_frames": n_view,
        "ball_raw_pct": 100.0 * raw[in_view].mean() if n_view else 0.0,
        "ball_clean_pct": 100.0 * np.isfinite(ball_px[in_view, 0]).mean() if n_view else 0.0,
        "near_pct": 100.0 * np.mean([c["near"] is not None for c, v in zip(chosen, in_view) if v]) if n_view else 0.0,
        "far_pct": 100.0 * np.mean([c["far"] is not None for c, v in zip(chosen, in_view) if v]) if n_view else 0.0,
        "shots": len(shots),
        "bounces": sum(s.bounce_frame is not None for s in shots),
        "rallies": len({s.rally for s in shots}),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--device", default="auto", help="auto | cuda | cpu")
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--near-hand", default="right", choices=["right", "left"])
    ap.add_argument("--far-hand", default="right", choices=["right", "left"])
    ap.add_argument("--me", default="near", choices=["near", "far"], help="which player is analysed as 'me'")
    ap.add_argument("--kind", default="reference", choices=["match", "training", "reference"])
    ap.add_argument("--source", default="broadcast", choices=["broadcast", "action_cam", "phone"])
    ap.add_argument("--surface", default=None)
    ap.add_argument("--player", default=None)
    ap.add_argument("--opponent", default=None)
    ap.add_argument("--notes", default=None)
    ap.add_argument("--no-video", action="store_true", help="skip the annotated video")
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--redo", action="store_true", help="ignore cached tracks")
    args = ap.parse_args()

    path = Path(args.video).resolve()
    info = video.probe(path)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{path.stem}_tracks.pkl"

    if cache.exists() and not args.redo:
        print(f"Using cached tracks: {cache.name}")
        tr = pickle.loads(cache.read_bytes())
    else:
        device = pick_device(args.device)
        print(f"Tracking {path.name}: {info.frames} frames, {info.width}x{info.height} @ {info.fps:.0f} fps on {device}")
        tr = track(path, device)
        cache.write_bytes(pickle.dumps(tr))

    hands = {"near": args.near_hand, "far": args.far_hand}
    ball_px, chosen, shots = analyse(info, tr, hands)
    s = summary(info, tr, ball_px, chosen, shots)
    print(f"Court in view: {s['court_view_frames']}/{s['frames']} frames")
    print(f"Ball tracked:  {s['ball_raw_pct']:.0f}% raw, {s['ball_clean_pct']:.0f}% after cleaning")
    print(f"Players found: near {s['near_pct']:.0f}%, far {s['far_pct']:.0f}%")
    print(f"Shots: {s['shots']} in {s['rallies']} rallies, {s['bounces']} with a bounce located")
    for sh in shots:
        b = f"bounce ({sh.bounce_xy_m[0]:+.1f}, {sh.bounce_xy_m[1]:+.1f}) m {'in' if sh.in_court else 'OUT'}" if sh.bounce_xy_m else "no bounce"
        spd = f"{sh.speed_kmh:.0f} km/h" if sh.speed_kmh else "-"
        print(f"  {sh.frame / info.fps:6.2f}s  rally {sh.rally} #{sh.seq}  {sh.hitter:4s} {sh.stroke:9s} {b:34s} {spd:9s} {sh.outcome}")

    if not args.no_db:
        con = db.connect(args.db)
        sid = db.save_session(con, info, shots, {
            "kind": args.kind, "source": args.source, "surface": args.surface, "player": args.player,
            "opponent": args.opponent, "notes": args.notes, "me_side": args.me,
            "camera_view": "broadcast" if args.source == "broadcast" else "behind_baseline",
        })
        con.close()
        print(f"Saved as session {sid} in {args.db}")

    if not args.no_video:
        out = OUT / f"{path.stem}_annotated.mp4"
        render.render(path, out, info, tr["Hs"], ball_px, chosen, shots)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
