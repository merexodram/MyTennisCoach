"""Streaming video access: frames are never all held in memory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass
class VideoInfo:
    path: Path
    fps: float
    width: int
    height: int
    frames: int

    @property
    def duration_s(self) -> float:
        return self.frames / self.fps if self.fps else 0.0


def probe(path: str | Path) -> VideoInfo:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    info = VideoInfo(
        Path(path),
        cap.get(cv2.CAP_PROP_FPS) or 25.0,
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    )
    cap.release()
    return info


def frames(path: str | Path) -> Iterator[tuple[int, np.ndarray]]:
    cap = cv2.VideoCapture(str(path))
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield i, frame
            i += 1
    finally:
        cap.release()


class Reader:
    """Random access to a video: read a run of consecutive frames from any start."""

    def __init__(self, path: str | Path):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {path}")
        self.pos = 0

    def read(self, start: int, count: int) -> list[np.ndarray]:
        if start != self.pos:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            self.pos = start
        out = []
        for _ in range(count):
            ok, frame = self.cap.read()
            if not ok:
                break
            out.append(frame)
            self.pos += 1
        return out

    def close(self) -> None:
        self.cap.release()
