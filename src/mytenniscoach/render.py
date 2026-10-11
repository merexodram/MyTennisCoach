"""Annotated output video: court lines, ball trail, players, events, mini-court."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import court, video

GREEN, YELLOW, RED, BLUE, WHITE, BLACK = (80, 220, 80), (0, 230, 255), (60, 60, 255), (255, 160, 60), (255, 255, 255), (0, 0, 0)
SIDE_COLOR = {"near": BLUE, "far": RED}


def _mini(shape, scale=7.0, margin=22):
    w = int(court.HALF_DOUBLES * 2 * scale) + 2 * margin
    h = int(court.HALF_LENGTH * 2 * scale) + 2 * margin
    to_px = lambda x, y: (int(w / 2 + x * scale), int(h / 2 + y * scale))
    base = np.full((h, w, 3), (120, 90, 40), np.uint8)
    for a, b in court.LINES:
        cv2.line(base, to_px(*court.KEYPOINTS_M[a]), to_px(*court.KEYPOINTS_M[b]), WHITE, 1, cv2.LINE_AA)
    cv2.line(base, to_px(-court.HALF_DOUBLES - 0.9, 0), to_px(court.HALF_DOUBLES + 0.9, 0), (200, 200, 200), 2)
    return base, to_px


def find_ffmpeg() -> str | None:
    """ffmpeg on PATH, or where winget puts it (PATH is stale until a new login)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    local = os.environ.get("LOCALAPPDATA")
    if local:
        hits = glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
                         recursive=True)
        if hits:
            return hits[0]
    return None


def to_h264(raw: Path, final: Path) -> bool:
    """OpenCV writes MPEG-4 Part 2, which Windows players and browsers often
    refuse. Re-encode to H.264 so the file plays anywhere."""
    exe = find_ffmpeg()
    if exe is None:
        return False
    cmd = [exe, "-y", "-v", "error", "-i", str(raw), "-c:v", "libx264", "-crf", "21",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)]
    return subprocess.call(cmd) == 0 and final.exists() and final.stat().st_size > 0


def _frames(path, n: int, keep):
    """All frames, or only those inside the kept [start, end) stretches."""
    if not keep or (len(keep) == 1 and keep[0][0] == 0 and keep[0][1] >= n):
        yield from video.frames(path)
        return
    reader = video.Reader(path)
    for a, b in keep:
        pos = a
        while pos < b:
            chunk = reader.read(pos, min(32, b - pos))
            if not chunk:
                break
            for frame in chunk:
                yield pos, frame
                pos += 1
    reader.close()


def render(path, out_path, info, Hs, ball_px, players, shots, keep=None):
    out_path = Path(out_path)
    raw_path = out_path.with_name(out_path.stem + "_raw.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(raw_path), fourcc, info.fps, (info.width, info.height))
    mini_base, to_mini = _mini((info.height, info.width))
    mh, mw = mini_base.shape[:2]
    hit_at = {s.frame: s for s in shots}
    bounce_at = {s.bounce_frame: s for s in shots if s.bounce_frame is not None}
    done: list = []
    label, label_until = "", -1

    for i, frame in _frames(path, len(Hs), keep):
        H = Hs[i]
        if H is not None:
            img_pts = court.to_image(H, court.KEYPOINTS_M)
            for a, b in court.LINES:
                cv2.line(frame, tuple(map(int, img_pts[a])), tuple(map(int, img_pts[b])), GREEN, 1, cv2.LINE_AA)
        for side in ("near", "far"):
            p = players[i].get(side)
            if p is not None:
                b = p[0]
                cv2.rectangle(frame, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), SIDE_COLOR[side], 2)
        for k in range(8):                                   # ball trail
            j = i - k
            if j >= 0 and np.isfinite(ball_px[j, 0]):
                cv2.circle(frame, (int(ball_px[j, 0]), int(ball_px[j, 1])), max(1, 5 - k // 2), YELLOW, -1, cv2.LINE_AA)

        if i in hit_at:
            s = hit_at[i]
            label, label_until = f"{s.hitter} {s.stroke}", i + int(info.fps * 1.2)
        if i in bounce_at:
            s = bounce_at[i]
            done.append(s)
            spd = f" {s.speed_kmh:.0f} km/h" if s.speed_kmh else ""
            label = f"bounce {'IN' if s.in_court else 'OUT'}{spd}"
            label_until = i + int(info.fps * 1.2)
        for s in done[-6:]:                                  # recent bounce marks on the real court
            if Hs[i] is not None:
                px = court.to_image(Hs[i], [s.bounce_xy_m])[0]
                cv2.drawMarker(frame, (int(px[0]), int(px[1])), GREEN if s.in_court else RED, cv2.MARKER_TILTED_CROSS, 10, 2)

        mini = mini_base.copy()
        for s in done:
            cv2.circle(mini, to_mini(*s.bounce_xy_m), 3, GREEN if s.in_court else RED, -1, cv2.LINE_AA)
        for side in ("near", "far"):
            p = players[i].get(side)
            if p is not None:
                cv2.circle(mini, to_mini(*p[1]), 5, SIDE_COLOR[side], -1, cv2.LINE_AA)
        x0, y0 = info.width - mw - 8, 8
        if y0 + mh < info.height:
            roi = frame[y0:y0 + mh, x0:x0 + mw]
            frame[y0:y0 + mh, x0:x0 + mw] = cv2.addWeighted(roi, 0.25, mini, 0.75, 0)

        cv2.putText(frame, f"{i / info.fps:6.2f}s", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLACK, 3, cv2.LINE_AA)
        cv2.putText(frame, f"{i / info.fps:6.2f}s", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 1, cv2.LINE_AA)
        if i <= label_until:
            cv2.putText(frame, label, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.75, BLACK, 4, cv2.LINE_AA)
            cv2.putText(frame, label, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.75, YELLOW, 2, cv2.LINE_AA)
        out.write(frame)
    out.release()
    if to_h264(raw_path, out_path):
        raw_path.unlink()
    else:
        raw_path.replace(out_path)
        print("  ffmpeg not found: the video is MPEG-4 Part 2 and may not play in every player. "
              "VLC plays it; installing ffmpeg fixes it.")
