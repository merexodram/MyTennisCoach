# The Phase 1 pipeline

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python -m mytenniscoach.process data\raw\clip.mp4 --far-hand left --player Federer --opponent Nadal
python scripts\report.py
python scripts\report.py --session 1
```

Output: an annotated video in `outputs\`, one session with its rallies and
shots in `data\tennis.duckdb`, and a cache of the per-frame tracks in
`outputs\cache\` (so changing the event rules and re-running takes seconds).

## What each stage does

| Stage | Module | How |
|---|---|---|
| Court | `court.py` | TennisCourtDetector network every 0.2 s gives 14 keypoints; a RANSAC homography maps image pixels to court metres (origin at the net centre, +y towards the camera). A frame counts as "court in view" only if at least 8 keypoints agree within 5 px, which is also what skips replays, close-ups and crowd shots. |
| Ball | `ball.py` | TrackNet on three stacked frames gives up to 4 candidate blobs per frame. Blobs that stay in one place are dropped (logos, a ball in a hand), the remaining path is followed by continuity, isolated jumps are removed and gaps up to 6 frames are interpolated. |
| Players | `players.py` | YOLOv8s finds every person. Feet are projected onto the court; people beside the net (umpire, ball kids) are excluded; within each half the tracked person who moves the most is the player. |
| Events | `events.py` | A hit is a reversal of the ball's vertical image direction next to a player, after which the ball really crosses to the other half. A bounce is the sharpest kink in the ball's path between two hits that maps into the target half. Bounce position, in/out, depth, direction and average speed (contact to bounce) follow from the homography. |
| Storage | `db.py` | One row per session, rally and shot. Re-processing a video replaces its rows. |
| Video | `render.py` | Court lines, ball trail, player boxes, event labels and a mini-court with bounce marks. |

## Own camera: mark the court once

The court network was trained on broadcast footage shot from high up. On a
club court filmed from a low camera it found the court in 0 of 1,633 frames.
For a camera that does not move, the fix is to mark the court by hand once:

1. Drag the video onto `calibrate.bat`.
2. Click the point named in the window title; press S for one you cannot see.
   Four points are the minimum, six or more across both halves are better. The
   fitted court is drawn in green so you can check it against the real lines.
3. Press Enter. `<video name>.court.json` is saved next to the video and
   `analyze.bat` uses it automatically.

First amateur test (8 s of a clay-court rally, camera about head height behind
the baseline, court marked from 10 hand-picked points): ball tracked in 71 % of
frames, both players found in every frame, 5 hits detected.

A low camera squeezes the far half of the court into very few pixels (51 pixel
rows for 12 m in that clip at 720p). Two things in the pipeline work against
that, and a third is up to the camera:

1. The working copy is 1080p, not 720p.
2. **Far-half zoom.** With a calibrated low camera, the ball network looks at
   the far half a second time, enlarged (2x in that clip). On the 8 s test this
   raised ball coverage from 71 % to 99 %; where both views saw the ball they
   agreed within about 1 pixel. It roughly doubles the ball-tracking time.
   `--far-zoom off` disables it.
3. Camera height. Depth on the far side (how deep a ball landed, in or out)
   still depends on how many pixel rows the far half gets. Higher is better;
   4K recording helps the far player's technique clips, not the depth.

Hit and bounce detection on the far side from a low camera is still weak: the
ball's up-and-down movement there is only a few pixels.

## What to trust, as of the first clips

| Output | Trust | Why |
|---|---|---|
| Court lines and homography | high | About 1 px reprojection error on broadcast footage |
| Which two people are the players | high | Correct on the test clips after the movement rule |
| Ball path | medium | Roughly 60 to 75 % of in-play frames at 480p; lost mostly near the players and at the far baseline |
| Hit count and who hit | medium | A hit is missed when the ball is not tracked around contact |
| Forehand / backhand | low | Only "which side of the body was the ball on"; needs pose (Phase 2) |
| Bounce position, in/out | low to medium | One pixel is 0.2 to 0.3 m at the far baseline; calls within 0.4 m of a line are flagged with confidence 0.5 |
| Speed | low | Average ground speed from contact to bounce, not racket speed |

## Speed: how a long recording is handled

Three things keep a two-hour session from taking days:

1. **Working copy.** Anything above 720p or 32 fps is first converted to a
   720p copy at 25 to 30 fps (`outputs\cache\<name>_proxy.mp4`). The networks
   look at 640x360 images anyway. The original is kept for cutting
   full-quality technique clips later.
2. **Scan for play.** Every 2 s, a burst of 8 frames is checked: is the court
   in view, and is a ball travelling on a smooth path? Only those stretches,
   padded by 3 s, get full tracking. `--all-frames` turns this off.
3. **Batches at half precision** on the GPU.

For a camera that does not move, add `--court-every 2` (or more): the court
is then detected every 2 s instead of five times a second.

Measured on the 4 GB laptop GPU, 3 min 25 s broadcast segment (1080p source):

| Version | Frames tracked | Time |
|---|---|---|
| First version, every frame | 5,134 | about 24 min |
| Working copy + scan + batches | 2,025 (40 %) | 10.8 min |

Where the 10.8 minutes went: ball network 436 s, scan 79 s, court 69 s,
players 60 s, decoding 4 s. The whole gain came from skipping footage. Per
tracked frame the cost stayed at about 0.27 s: the ball network (TrackNet) is
the bottleneck, and half precision passes its self-check but brings no speed
on this card. Since then, frames inside a kept stretch where the court is out
of view are skipped as well, and the padding is 2 s instead of 3 s.

The annotated video contains only the kept stretches; `--full-video` gives the
whole recording.

The scan has only been tested on broadcast footage, where the court check does
most of the work. On a fixed own camera the court is always in view, so the
ball-path check decides alone; that needs testing on real own footage.

The log ends with a line such as
`tracking took 4.0 min (scan 0s, decode 0s, court 30s, ball 187s, players 22s)`,
which shows where the time goes.
