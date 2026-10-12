# MyTennisCoach

A personal tennis coach built from match and training video: a computer-vision
pipeline turns footage into shot-by-shot data, a small database keeps the
numbers so the video itself can be deleted, and an AI coach reads the data plus
a few key frames to review technique, tactics and progress over time.

**Status: Phase 1, first working pipeline.** A video goes in; court, ball and
both players are tracked; hits and bounces are detected; rallies and shots are
written to the database; an annotated video comes out. Tested on four 20 s
broadcast clips at 480p. Tracking is solid, event detection is a first version
(see [docs/PIPELINE.md](docs/PIPELINE.md) for what to trust). Not yet tested on
own-camera footage or on a GPU.

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
| Events | Hits, bounces, placement, rallies | this repository (`events.py`), first version |
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

Or simply double-click `setup.bat`. To get footage, put video links in
`data\links.txt` and double-click `download.bat`. Then drag a video onto `analyze.bat`
to process it, and see [docs/PIPELINE.md](docs/PIPELINE.md) for options and
`scripts/report.py` for statistics.
Full prerequisites are in [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md).

## Privacy

This repository is public, so it holds code and documentation only. Footage,
pictures, court clicks, player settings, statistics, reviews, databases, logs
and credentials stay on the laptop: `data/`, `outputs/` and `models/` are never
committed, and `.gitignore` blocks those file types wherever they are.
`scripts/check_public.py` checks files, history and commit messages for
personal data and secrets; it also reads a local list of private words from
`data/private_terms.txt` (never published). GitHub runs the same check on
every push (`.github/workflows/privacy.yml`).


## Repository layout

```
docs/            setup, validation protocol, upstream credits
scripts/         setup, weights download, clip fetch, statistics report, baseline run
setup.bat        one-click install         analyze.bat   drag a video onto it
download.bat     download the links in data\links.txt (yt-dlp, up to 1080p)
calibrate.bat    own camera: click the court points and yourself, once per camera position
prepare_colab.bat  get a recording ready for tracking on a free Colab GPU (docs/COLAB.md)
coach.bat        after analysing: coach pack, store the review, update metrics, Obsidian notes, dashboard (docs/COACH.md)
compare.bat      compare any two sessions in Obsidian (outputs\dashboard.html compares any pair in the browser)
docs/METRICS.md  the ~100 session metrics, professional-statistics style, and where each comes from
tests/           python -m pytest tests
.github/         privacy check on every push
src/mytenniscoach/   the pipeline: court, ball, players, events, db, render, process
third_party/     upstream repositories as pinned submodules
data/            footage, clips and tennis.duckdb   (local only, git-ignored)
models/          pretrained weights                 (local only, git-ignored)
outputs/         annotated videos                   (local only, git-ignored)
```

## Roadmap

| Phase | Goal | Done when |
|---|---|---|
| 0 Validation | Run upstream models on professional broadcast clips | Tracking quality judged good enough to continue ([criteria](docs/VALIDATION.md)) |
| 1 Tracking | Own pipeline: court + TrackNet ball + players, streaming (no full video in RAM), results written to the database | A full match processes unattended and fills `sessions` and `shots`. **In progress: works on clips; full match and GPU run still to do** |
| 2 Technique | Pose, stroke classification, per-stroke metrics, clip retention | `pose_metrics` filled; raw video can be deleted. **Started: pose and first measurements for the marked player** |
| 3 Coach | Session review and monthly trend review | Review generated from the database after each session. **Built: pack, clips, review storage, session metrics, 3D ball flight estimate, Obsidian notes and comparison dashboard; first real review waits for own footage** |
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
