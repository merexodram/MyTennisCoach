"""Mark the court by hand for a camera that does not move.

    python scripts/calibrate.py data/raw/my_session.mp4

A frame of the video opens. The window title names one court point at a
time. Click it, or press S to skip a point you cannot see. Four points are the
minimum; six or more, spread over both halves, are better. The fitted court is
drawn in green as soon as four points are set, so you can see whether it sits
on the real lines.

    click      set the point named in the title
    S          skip this point
    U          undo the last point
    N          show another frame of the video (if a player hides a line)
    Enter      save and quit (needs 4 points)

The last thing asked is to click on yourself. Players change ends, so the
pipeline uses the colours of your clothes to know which player is you in
every rally. Wear something different from your opponent.
    Esc        quit without saving

The result is saved next to the video as <name>.court.json and used
automatically by analyze.bat.

A magnifier in a corner shows the spot under the mouse four times enlarged.
A click on a near-half point is moved onto the real crossing of the two
painted lines next to it when one is found; far-half points stay where you
click, so use the magnifier there. A point that disagrees with the others is ringed in
red with "check": press U until it is undone and click it again, or skip it.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mytenniscoach import court, video  # noqa: E402

# Easiest points first: the near half is large on screen.
ME = "me"
ORDER = [2, 3, 5, 7, 10, 11, 13, court.NET_CENTRE, 1, 0, 6, 4, 9, 8, 12, ME]
# Near-half points are snapped onto the painted lines. On the far half the net
# tape runs through the picture and would be mistaken for a court line.
SNAP = {2, 3, 5, 7, 10, 11, 13}
WINDOW = "MyTennisCoach court calibration"


def draw(frame: np.ndarray, points: dict, scale: float, me_point=None, cursor=None) -> np.ndarray:
    img = frame.copy()
    errors = court.point_errors(points)
    limit = max(6.0, frame.shape[1] / 1920 * 8.0)
    H, err = court.fit_points(points)
    if H is not None:
        ip = court.to_image(H, court.KEYPOINTS_M)
        for a, b in court.LINES:
            cv2.line(img, tuple(map(int, ip[a])), tuple(map(int, ip[b])), (0, 255, 0), 2, cv2.LINE_AA)
        net = court.to_image(H, [(-court.HALF_DOUBLES, 0.0), (court.HALF_DOUBLES, 0.0)])
        cv2.line(img, tuple(map(int, net[0])), tuple(map(int, net[1])), (255, 0, 255), 2, cv2.LINE_AA)
    for key, (x, y) in points.items():
        bad = errors.get(key, 0.0) > limit                  # disagrees with the other points: probably misclicked
        cv2.circle(img, (int(x), int(y)), 6, (0, 0, 255), -1, cv2.LINE_AA)
        if bad:
            cv2.circle(img, (int(x), int(y)), 18, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.putText(img, "check", (int(x) + 20, int(y) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
    if me_point is not None:
        cv2.circle(img, (int(me_point[0]), int(me_point[1])), 14, (0, 255, 255), 3, cv2.LINE_AA)
    out = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale != 1 else img
    if cursor is not None:                                  # magnifier: 4x view of what is under the mouse
        cx, cy = int(cursor[0]), int(cursor[1])
        r = 30
        x0, y0 = max(0, cx - r), max(0, cy - r)
        patch = frame[y0: cy + r, x0: cx + r]
        if patch.size:
            lens = cv2.resize(patch, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            lh, lw = lens.shape[:2]
            mx, my = (cx - x0) * 4, (cy - y0) * 4
            cv2.line(lens, (mx - 14, my), (mx + 14, my), (0, 255, 255), 1)
            cv2.line(lens, (mx, my - 14), (mx, my + 14), (0, 255, 255), 1)
            cv2.rectangle(lens, (0, 0), (lw - 1, lh - 1), (0, 255, 255), 2)
            # Put it in the corner away from the mouse.
            ox = 10 if cx * scale > out.shape[1] / 2 else out.shape[1] - lw - 10
            oy = 10 if cy * scale > out.shape[0] / 2 else out.shape[0] - lh - 10
            if ox >= 0 and oy >= 0 and oy + lh <= out.shape[0] and ox + lw <= out.shape[1]:
                out = out.copy()
                out[oy: oy + lh, ox: ox + lw] = lens
    return out


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1]).resolve()
    info = video.probe(path)
    reader = video.Reader(path)
    at = min(info.frames - 1, int(info.fps * 5))
    frame = reader.read(at, 1)[0]
    scale = min(1.0, 1600 / info.width, 900 / info.height)      # fit the screen

    points: dict = {}
    me = None
    history: list = []
    idx = 0
    clicked: list = []
    cv2.namedWindow(WINDOW)
    cursor: list = [None]

    def on_mouse(ev, x, y, *_):
        cursor[0] = (x / scale, y / scale)
        if ev == cv2.EVENT_LBUTTONDOWN:
            clicked.append((x / scale, y / scale))

    cv2.setMouseCallback(WINDOW, on_mouse)
    while True:
        key_name = ORDER[idx] if idx < len(ORDER) else None
        if key_name == ME:
            label = "YOURSELF, on your shirt (so the coach knows which player is you)"
        else:
            label = court.POINT_NAMES[key_name] if key_name is not None else "all done, press Enter"
        cv2.setWindowTitle(WINDOW, f"Click: {label}   |   S skip, U undo, N other frame, Enter save, Esc quit   "
                                   f"[{len(points)} set]")
        cv2.imshow(WINDOW, draw(frame, points, scale, me["point"] if me else None, cursor[0]))
        k = cv2.waitKey(30) & 0xFF
        if clicked and key_name == ME:
            me = {"frame": int(at), "fps": float(info.fps), "point": [float(v) for v in clicked.pop()]}
            clicked.clear()
            history.append(ME)
            idx += 1
        elif clicked and key_name is not None:
            spot = clicked.pop()
            if key_name in SNAP:
                spot, _ = court.snap_to_lines(frame, spot)
            points[key_name] = spot
            clicked.clear()
            history.append(key_name)
            idx += 1
        elif k in (ord("s"), ord("S")) and key_name is not None:
            idx += 1
        elif k in (ord("u"), ord("U")) and history:
            last = history.pop()
            if last == ME:
                me = None
            points.pop(last, None)
            idx = ORDER.index(last)
        elif k in (ord("n"), ord("N")):
            at = (at + int(info.fps * 3)) % max(1, info.frames - 1)
            got = reader.read(at, 1)
            if got:
                frame = got[0]
        elif k == 13 and len(points) >= 4:
            out = court.calibration_file(path)
            court.save_calibration(out, points, (info.width, info.height), me)
            H, err = court.fit_points(points)
            print(f"Saved {out} ({len(points)} points, worst fit error {err:.1f} px, "
                  f"{'you are marked' if me else 'you are NOT marked: the near player is taken as you'})")
            break
        elif k == 27:
            print("Nothing saved.")
            break
        clicked.clear()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
