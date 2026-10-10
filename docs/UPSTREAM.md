# Upstream repositories

Checked on 2026-10-09. Each upstream is a git submodule under `third_party/`,
pinned to the commit below, so the project is reproducible and every line of
borrowed code stays attributed to its author.

| Submodule | Upstream | Pinned commit | Commit date | Licence file |
|---|---|---|---|---|
| `third_party/tennis_analysis` | https://github.com/abdullahtarek/tennis_analysis | `d557527` | 2024-03-22 | none |
| `third_party/TrackNet` | https://github.com/yastrebksv/TrackNet | `730ea17` | 2024-03-17 | none |
| `third_party/TennisCourtDetector` | https://github.com/yastrebksv/TennisCourtDetector | `e5cd4f1` | 2024-03-15 | none |
| `third_party/SwingForge` | https://github.com/SinbadSails/SwingForge | `00c3984` | 2026-03-25 | none |

## What "no licence file" means

A public GitHub repository without a licence is still under its author's
copyright. GitHub's terms let anyone view and fork it on GitHub, and you can
clone and run it for yourself, but there is no explicit permission to copy the
code into another project or redistribute modified versions.

That is why this project:

- references the upstreams (through forks) as submodules instead of copying files,
- wraps and calls upstream code rather than editing it in place,
- writes its own modules in `src/mytenniscoach/` for anything that needs to
  behave differently.

If the project should ever become a tool other people install, ask each author
to add a licence (an issue on their repository is the usual way), or replace
that component with a permissively licensed one. A candidate for the ball
tracker is [qaz812345/TrackNetV3](https://github.com/qaz812345/TrackNetV3)
(MIT). It is trained on badminton, so it would need retraining on tennis data.

## Video download

Videos are downloaded with [yt-dlp](https://github.com/yt-dlp/yt-dlp)
(Unlicense, public domain). It is installed as a Python package and updated on
every `download.bat` run, because video sites change often; it is not forked
or copied here. See `scripts/fetch_video.py`.

## Pretrained weights

`scripts/download_weights.py` downloads weights from the Google Drive links the
authors publish in their READMEs. Weights are stored in `models/` and are not
committed.

## Datasets (for later fine-tuning)

- TrackNet tennis ball dataset: 19,835 labelled frames from 10 broadcast videos (linked in the TrackNet README)
- TennisCourtDetector dataset: 8,841 images with 14 keypoints (linked in its README)

## Forks

Each upstream is forked under `merexodram` (2026-10-09), and the submodules
point at the forks. The forks keep a copy in case an upstream disappears and
are the place for any changes to upstream code. GitHub shows "forked from ..."
on each, which is the attribution.

| Fork | Forked from |
|---|---|
| https://github.com/merexodram/tennis_analysis | abdullahtarek/tennis_analysis |
| https://github.com/merexodram/TrackNet | yastrebksv/TrackNet |
| https://github.com/merexodram/TennisCourtDetector | yastrebksv/TennisCourtDetector |
| https://github.com/merexodram/SwingForge | SinbadSails/SwingForge |

To pull in later upstream changes, use **Sync fork** on the fork's GitHub page,
then update the pinned commit here with `git submodule update --remote <path>`.

## Papers

- Huang et al., *TrackNet: A Deep Learning Network for Tracking High-speed and Tiny Objects in Sports Applications*, 2019. https://arxiv.org/abs/1907.03698
