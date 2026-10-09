# Phase 0: validation on professional footage

Goal: decide, before buying a camera, whether the open-source vision models
are good enough to build a coach on.

## What this test can and cannot tell you

The pretrained models were trained on broadcast tennis. Professional match
footage is therefore the easiest case for them:

- If tracking is poor here, the approach needs different models. Stop and rethink.
- If tracking is good here, the pipeline works, but it does not yet prove it
  will work from an action camera on your court. That is the second check
  below, and it costs nothing.

Nothing is trained on these clips. They are test input, and later a source of
reference technique for comparison.

## Choosing clips

- Main broadcast camera, behind the baseline, high. Full-match uploads work
  better than highlight reels, which cut between angles.
- One continuous rally per clip, 20 to 40 seconds, no replays or close-ups.
- 720p is enough (the models work at 1280x720).
- Take 5 or 6 clips across surfaces: hard, clay, grass, and one indoor.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\fetch_video.py "<video url>" --name federer_hard_01 --start 00:12:30 --end 00:13:05
python scripts\run_baseline.py data\raw\federer_hard_01.mp4
```

Open `outputs\federer_hard_01_baseline.avi` and score it.

## Scorecard

Fill one row per clip in `docs/validation_log.md`.

| Check | How to judge | Good enough |
|---|---|---|
| Court keypoints | All 14 points sit on line intersections | No point off by more than a line width |
| Player tracking | Boxes stay on the two players, IDs do not swap | No swaps, no ball kids picked up |
| Ball detection | Ball box present while the ball is in flight | Visible in most frames; gaps mainly at contact and bounce |
| Shot count | Count hits by eye, compare with the overlay | Within one or two shots per rally |
| Mini-court | Player dots match real positions | Correct side and roughly correct depth |

## Second check, before buying a camera

Record 10 minutes of your own hitting with a phone clamped high on the back
fence, centred, 1080p at 60 fps, and run the same command. Expect it to be
clearly worse than the broadcast clips. What matters is how it fails:

- Court keypoints wrong: camera too low or too close. Fixable by placement.
- Ball lost most of the time: needs fine-tuning on your footage. Planned in Phase 1.
- Players fine, ball partly fine: proceed, buy the camera.

## Decision

Continue to Phase 1 when the broadcast clips pass the scorecard and the phone
test fails only in ways listed above.
