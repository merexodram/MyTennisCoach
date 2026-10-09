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
