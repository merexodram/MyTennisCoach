# MyTennisCoach

A personal tennis coach built from match and training video: a computer-vision
pipeline turns footage into shot-by-shot data, a small database keeps the
numbers so the video itself can be deleted, and an AI coach reads the data plus
a few key frames to review technique, tactics and progress over time.

**Status: Phase 0, validation.** The repository currently contains the project
skeleton, the database schema, setup scripts and a wrapper that runs an
existing open-source tracker on a test clip. No own analysis code yet.

## How it works

```
 video ──> vision ──────────> events ──────────> database ──> coach
 (cam)     court keypoints    hits, bounces      DuckDB       session review,
           ball trajectory    stroke type        sessions     monthly trends,
           player tracking    in / out           points       tactics, drills
           body pose          points, rallies    shots
                                                 pose_metrics
                                                 clips (few seconds, flagged shots only)
```

| Stage | What it does | Built on |
|---|---|---|
| Court | 14 court keypoints, homography from image to court metres | TennisCourtDetector |
| Ball | Ball trajectory and bounce detection | TrackNet |
| Players | Detection and tracking | YOLOv8 (ultralytics) |
| Pose | 33 body keypoints, joint angles, swing phases | MediaPipe, SwingForge |
| Events | Hits, stroke type, placement, points | this repository (planned) |
| Storage | One DuckDB file, schema in `src/mytenniscoach/schema.sql` | this repository |
| Coach | Review written from statistics and key frames | this repository (planned) |

## Built on other people's work

This project stands on four upstream repositories. Each is forked under
`merexodram` and referenced as a git submodule pinned to an exact commit under
`third_party/`; none of their code is copied into this repository. Details and
licence status are in [docs/UPSTREAM.md](docs/UPSTREAM.md).

| Upstream | Author | Used for |
|---|---|---|
| [tennis_analysis](https://github.com/abdullahtarek/tennis_analysis) | Abdullah Tarek | Baseline end-to-end pipeline (players, ball, court, mini-court, speeds) |
| [TrackNet](https://github.com/yastrebksv/TrackNet) | yastrebksv | Ball tracking and bounce detection (implementation of [Huang et al. 2019](https://arxiv.org/abs/1907.03698)) |
| [TennisCourtDetector](https://github.com/yastrebksv/TennisCourtDetector) | yastrebksv | Court keypoints with homography refinement |
| [SwingForge](https://github.com/SinbadSails/SwingForge) | SinbadSails | Pose engine, swing detection and stroke classification |

Also used as libraries: [Ultralytics YOLO](https://github.com/ultralytics/ultralytics),
[MediaPipe](https://github.com/google-ai-edge/mediapipe), [DuckDB](https://duckdb.org),
[yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Quick start (Windows)

```powershell
git clone --recurse-submodules --shallow-submodules https://github.com/merexodram/MyTennisCoach.git F:\MyTennisCoach
cd F:\MyTennisCoach
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Then follow [docs/VALIDATION.md](docs/VALIDATION.md) to run the first test clip.
Full prerequisites are in [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md).

## Repository layout

```
docs/            setup, validation protocol, upstream credits
scripts/         setup, weights download, clip fetch, baseline run, database init
src/mytenniscoach/   own code; currently the database schema
third_party/     upstream repositories as pinned submodules
data/            footage, clips and tennis.duckdb   (local only, git-ignored)
models/          pretrained weights                 (local only, git-ignored)
outputs/         annotated videos                   (local only, git-ignored)
```

## Roadmap

| Phase | Goal | Done when |
|---|---|---|
| 0 Validation | Run upstream models on professional broadcast clips | Tracking quality judged good enough to continue ([criteria](docs/VALIDATION.md)) |
| 1 Tracking | Own pipeline: court + TrackNet ball + players, streaming (no full video in RAM), results written to the database | A full match processes unattended and fills `sessions` and `shots` |
| 2 Technique | Pose, stroke classification, per-stroke metrics, clip retention | `pose_metrics` filled; raw video can be deleted |
| 3 Coach | Session review and monthly trend review | Review generated from the database after each session |
| 4 Match logic | Points, score, forced and unforced errors, opponent patterns | `points` filled automatically |

Own-camera footage enters between Phase 0 and Phase 1: a phone on the back
fence first, an action camera once the approach is proven.

## Known limits

- One camera gives reliable placement, counts and patterns. Ball speed and spin
  are estimates.
- The pretrained models were trained on broadcast footage. Amateur footage from
  a lower, wider camera will need fine-tuning.
- The far-side player is small in frame, so pose metrics are trustworthy for the
  near player only.

## Footage and privacy

No video, model weights or personal data are stored in this repository.
Broadcast clips used for validation are copyrighted and stay on the local disk
for private testing only. Ask the people on court before recording them.

## Licence

No licence has been chosen yet for the code in this repository. Upstream
repositories keep their own terms, see [docs/UPSTREAM.md](docs/UPSTREAM.md).
