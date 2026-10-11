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

from . import activity, ball, court, db, events, players, proxy, render, video

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
CACHE = OUT / "cache"


def pick_device(name: str) -> str:
    if name != "auto":
        return name
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def track(path: Path, device: str, court_every_s: float = 0.2, log=print, checkpoint: Path | None = None,
          scan: bool = True, batch: int | None = None, min_scan_s: float = 60.0) -> dict:
    """Court, ball and players for every frame worth looking at.

    1. Scan: short bursts through the ball network find where a ball is in play.
    2. Track: only those stretches get the full treatment, in batches.
    Progress is saved regularly; an interrupted run resumes where it stopped.
    """
    info = video.probe(path)
    n = info.frames
    step = max(1, int(round(info.fps * court_every_s)))
    batch = batch or (8 if device.startswith("cuda") else 2)
    cd, bt, pf = court.CourtDetector(device), ball.BallTracker(device), players.PlayerFinder(device)
    empty = np.zeros((0, 5), np.float32)
    clock = {"scan": 0.0, "decode": 0.0, "court": 0.0, "ball": 0.0, "players": 0.0}

    state = None
    if checkpoint is not None and checkpoint.exists():
        state = pickle.loads(checkpoint.read_bytes())
        if "windows" not in state:
            state = None                                   # checkpoint from an older version
    if state is None:
        t = time.time()
        if scan and n > info.fps * min_scan_s:             # not worth it for clips under a minute
            windows = activity.find_windows(path, info, bt, cd, log=log)
        else:
            windows = [(0, n)]
        clock["scan"] = time.time() - t
        state = {"windows": windows, "next": 0,
                 "tr": {"Hs": [None] * n, "court_err": [float("inf")] * n, "ball": [None] * n,
                        "boxes": [empty] * n}}
    else:
        log(f"  resuming at frame {state['next']}")
    windows, tr = state["windows"], state["tr"]
    todo = sum(b - a for a, b in windows)
    log(f"  ball in play in {len(windows)} stretch(es): {todo} of {n} frames ({100 * todo / max(n, 1):.0f}%) to track")

    reader = video.Reader(path)
    done, t0, last_save = 0, time.time(), time.time()
    for a, b in windows:
        if b <= state["next"]:
            done += b - a
            continue
        i = max(a, state["next"])
        done += i - a
        bt.reset()
        H, err = None, float("inf")
        if i > a:                                          # resuming inside a stretch
            bt.infer(reader.read(max(a, i - 2), i - max(a, i - 2)))
            H, err = tr["Hs"][i - 1], tr["court_err"][i - 1]
        while i < b:
            t = time.time()
            frames = reader.read(i, min(batch, b - i))
            clock["decode"] += time.time() - t
            if not frames:
                break
            t = time.time()
            for k, frame in enumerate(frames):
                if (i + k - a) % step == 0:
                    kps = cd.keypoints(frame)
                    H, n_inl, err = court.fit_homography(kps)
                    if H is not None and (n_inl < 8 or err > 5.0):
                        H = None                           # not the main camera view
                tr["Hs"][i + k], tr["court_err"][i + k] = H, err
            clock["court"] += time.time() - t
            t = time.time()
            blobs = bt.infer(frames)
            clock["ball"] += time.time() - t
            t = time.time()
            in_view = [k for k in range(len(frames)) if tr["Hs"][i + k] is not None]
            found = pf.people_batch([frames[k] for k in in_view])
            clock["players"] += time.time() - t
            for k, boxes in zip(in_view, found):
                tr["ball"][i + k] = blobs[k]
                tr["boxes"][i + k] = boxes
            before = done
            i += len(frames)
            done += len(frames)
            state["next"] = i
            if done // 250 != before // 250:
                rate = (time.time() - t0) / max(1, done)
                log(f"  {done}/{todo} frames  {rate:.3f} s/frame  about {rate * (todo - done) / 60:.0f} min left")
            if checkpoint is not None and time.time() - last_save > 120:
                checkpoint.write_bytes(pickle.dumps(state))
                last_save = time.time()
    reader.close()
    if checkpoint is not None and checkpoint.exists():
        checkpoint.unlink()
    total = time.time() - t0 + clock["scan"]
    parts = ", ".join(f"{k} {v:.0f}s" for k, v in clock.items())
    log(f"  tracking took {total / 60:.1f} min ({parts})")
    tr["windows"] = windows
    return tr


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
    ap.add_argument("--all-frames", action="store_true", help="track every frame instead of only where a ball is in play")
    ap.add_argument("--no-proxy", action="store_true", help="analyse the original file, not a 720p working copy")
    ap.add_argument("--court-every", type=float, default=0.2,
                    help="seconds between court detections (use 2 or more for a fixed camera)")
    args = ap.parse_args()

    original = Path(args.video).resolve()
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{original.stem}_tracks.pkl"
    # Work on a 720p copy when the recording is larger or faster than needed.
    path = original if args.no_proxy else proxy.make(original, CACHE / f"{original.stem}_proxy.mp4")
    info = video.probe(path)

    if cache.exists() and not args.redo:
        print(f"Using cached tracks: {cache.name}")
        tr = pickle.loads(cache.read_bytes())
    else:
        device = pick_device(args.device)
        print(f"Tracking {path.name}: {info.frames} frames, {info.width}x{info.height} @ {info.fps:.0f} fps on {device}")
        tr = track(path, device, checkpoint=CACHE / f"{original.stem}_partial.pkl",
                   scan=not args.all_frames, court_every_s=args.court_every)
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
        info.path = original                               # the session belongs to the recording, not its copy
        sid = db.save_session(con, info, shots, {
            "kind": args.kind, "source": args.source, "surface": args.surface, "player": args.player,
            "opponent": args.opponent, "notes": args.notes, "me_side": args.me,
            "camera_view": "broadcast" if args.source == "broadcast" else "behind_baseline",
        })
        con.close()
        print(f"Saved as session {sid} in {args.db}")

    if not args.no_video:
        out = OUT / f"{original.stem}_annotated.mp4"
        render.render(path, out, info, tr["Hs"], ball_px, chosen, shots)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
