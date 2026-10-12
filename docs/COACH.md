# The coach

Three layers, kept apart on purpose:

| Layer | What it is | Where |
|---|---|---|
| Facts | Rallies, shots, technique numbers, tracking quality | `data\tennis.duckdb` |
| Metrics | One value per session for each of the metrics in [METRICS.md](METRICS.md): serve, return, rally, errors, ball flight, movement, technique, score, how it felt | `session_metrics` in the database |
| Coach pack | The facts of one session laid out for reading, with picture strips of key strokes and the earlier sessions for comparison | `outputs\coach\session_NNNN\pack.md` |
| Review | What the facts mean: what went well, 2 to 3 priorities, drills | written by Claude from the pack, stored in the database, `data\reviews\` and your Obsidian file |

The pack never interprets. The review never invents numbers: everything in it
must be traceable to the pack, and it must respect the "how much the tracking
saw" section.

## After a session

1. `calibrate.bat` (once per camera position), then `analyze.bat` or the Colab route.
2. Double-click `coach.bat`. It writes the coach pack for the latest session.
3. Ask Claude: "review my last tennis session". Claude reads the pack and the
   picture strips, asks for what the camera cannot see (score, break points,
   how it felt, corrections), and writes `review.md` and `coach_input.json`
   into the same folder.
4. Double-click `coach.bat` again. It stores the review and your answers,
   recomputes the metrics of all sessions, and rewrites the Obsidian notes
   and `outputs\dashboard.html`.

Step 4 exists because Claude can read and write files in this folder but
cannot run programs on the laptop.

## What a review contains

1. **Session at a glance**: what was played, how much of it the tracking saw.
2. **What the numbers say**: strokes, placement, errors, rally lengths, against earlier sessions.
3. **Technique**: per stroke, from the pose numbers and the picture strips.
4. **Priorities**: two or three, each tied to a number or a picture.
5. **Drills**: one per priority.
6. **Open questions**: what could not be judged from this recording.

## Clips and deleting the recording

`analyze.bat` keeps 3-second clips of flagged strokes in `data\clips\`: every
error, the fastest shots that landed in, and one of each stroke as a reference.
Reference clips are kept; the others carry a keep-until date six months ahead.
Once the review is stored, the original recording is no longer needed by the
pipeline. Deleting it is left to you.

## Comparing sessions

- `outputs\dashboard.html`: pick any session and compare it with the previous
  one, your best ever, the average of the five before, or any other session.
  Click a metric for its trend. Filter matches or trainings.
- Obsidian, folder `Tennis` (see Settings): `Tennis.md` is the home note
  (latest against previous and best, records, trend of the last eight
  sessions); `Sessions\` has one note per session with every metric as a
  property; `Sessions.base` is a sortable table of all sessions (Obsidian
  Bases, works on the iPhone); `Compare\` holds latest vs previous, vs best,
  vs the last-5 average, and any pair made with `compare.bat 3 7`.
- Pro footage (`reference` sessions) is never compared with your own.

## Settings

`data\player.json`:

```json
{ "hand": "right", "backhand": "two", "height_cm": 180, "default_kind": "training",
  "obsidian_dir": "G:\\My Drive\\MyVault\\Tennis",
  "obsidian_file": "C:\\path\\to\\MyVault\\Sports.md" }
```

- `default_kind`: what a session of your own is unless you say otherwise (`training` or `match`); tell the coach if it was a match.
- `obsidian_dir`: where the Tennis notes are written, normally the `Tennis`
  folder inside your vault. If Google Drive for desktop syncs the vault, point
  it there and the notes reach Drive by themselves. Without it the notes go to
  `outputs\obsidian\Tennis` and Claude uploads them to Drive after a review.
  The Bases table expects the folder to be `Tennis` at the top of the vault.
- `obsidian_file` (optional): each stored review is also appended to this note.

The session date is taken from the recording's file date; `analyze.bat` also
accepts `--date 2026-10-14`. A session with a clicked court file is stored as
your own camera (`action_cam`), anything else as broadcast `reference`.
