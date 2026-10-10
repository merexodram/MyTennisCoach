# Validation log

| Date | Clip | Surface | Court | Players | Ball | Shots (seen / counted) | Mini-court | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-10 | federer_ao17_01 (AO 2017 final, 480p, 19.5 s) | hard | pass | fail | fail | n/a / 0 | fail | Baseline run on CPU. Court keypoints sit on the line intersections. Near player tracked correctly; far "player" is a line judge, not the opponent. Ball found in 88 of 488 frames. Shot statistics empty. Clip includes time between points. |

## Findings so far

1. **Court keypoint model works** on broadcast footage, even at 480p.
2. **Player selection is the weak part of the baseline, not detection.** YOLO finds all 8 to 10 people in frame; upstream then keeps the two nearest a court keypoint in the first frame and assumes their track ids are 1 and 2. With officials and ball kids in frame, both assumptions fail. Fix in Phase 1: select players by position inside the court homography, per frame.
3. **Per-frame YOLO ball detection is not good enough** (18 % of frames). This is the reason TrackNet is in the plan; test it next on the same clip.
4. **Upstream shot detection silently returns nothing under pandas 3** (chained assignment). `requirements.txt` now pins pandas below 3.
5. `run_baseline.py` now caches detections per clip, skips an unneeded 100 MB ImageNet download, and renumbers the chosen players so the upstream code does not crash.

## Phase 1 pipeline, night run of 2026-10-10

Four clips from the AO 2017 final (854x480, 25 fps, about 20 s each), processed
on a 2-core CPU at 6 to 8 s per frame.

| Clip | Court in view | Players near / far | Ball, raw / cleaned | Shots found | Bounces located |
|---|---|---|---|---|---|
| 01 | 488 / 488 | 100 % / 98 % | 43 % / 33 % | 3 | 3 |
| 02 | 505 / 505 | 99 % / 94 % | 70 % / 57 % | 7 | 5 |
| 03 | 480 / 500 | 100 % / 100 % | 68 % / 49 % | 5 | 2 |
| 04 | 440 / 475 | 100 % / 92 % | 46 % / 33 % | 2 | 1 |

Ball percentages are over all court-view frames, including the time between
points when no ball is in play, and "cleaned" also drops a ball that is
being bounced on the spot before a serve. They understate in-play coverage.

Checked by eye on extracted frames:

- **Court lines:** overlay sits on the real lines in every frame looked at.
- **Players:** the right two people in every frame looked at, including with
  the far player standing 5 m behind the baseline. The baseline's failure
  (picking a line judge) is gone.
- **Hits:** clip 02 has a 7-shot rally by eye (serve and six strokes); the
  pipeline found 6 of them and missed the return of serve, where the ball was
  not tracked beyond the far baseline.
- **Bounces and speeds: not yet trustworthy.** Several bounce marks sit near the
  net where no bounce is visible, and the far player's serve speeds come out
  near 67 km/h, which is clearly wrong. Hit timing on the far side is late
  (detected at the top of the ball's arc rather than at contact).

Next for events: use the hit player's position to time far-side contacts, fit
a ballistic arc between hits to place the bounce instead of looking for a
kink, and label one full game by hand to measure hit and bounce accuracy
instead of judging by eye.

## Event logic, second version (2026-10-10, morning)

First run on the 4 GB laptop GPU: 0.31 s per frame for clip 02 (about 20 times the
CPU speed), same tracking quality.

Changes: contact time is moved from the direction reversal to the frame where
the ball is closest to the player; a longer blind spell is allowed around the
far player; a stall just before contact no longer hides the hit; bounces are
found by fitting two arcs to the ball's image path instead of looking for one
kink.

Clip 02, rally of serve plus six strokes counted by eye:

| | Version 1 | Version 2 |
|---|---|---|
| Hits found in the rally | 6 of 7 | 7 of 7, alternating near and far correctly |
| Bounces located | 5 | 6 |

Near-side bounces now land where the near player then hits the ball, which is
a useful self-check. Far-side bounces are still doubtful (the serve bounce is
placed at the net), and far-side serve speeds are still far too low. The last
shot of the clip ends at the net and is labelled a winner; it should be a net
error.
