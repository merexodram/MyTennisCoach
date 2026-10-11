# The coach

Three layers, kept apart on purpose:

| Layer | What it is | Where |
|---|---|---|
| Facts | Rallies, shots, technique numbers, tracking quality | `data\tennis.duckdb` |
| Coach pack | The facts of one session laid out for reading, with picture strips of key strokes and the earlier sessions for comparison | `outputs\coach\session_NNNN\pack.md` |
| Review | What the facts mean: what went well, 2 to 3 priorities, drills | written by Claude from the pack, stored in the database, `data\reviews\` and your Obsidian file |

The pack never interprets. The review never invents numbers: everything in it
must be traceable to the pack, and it must respect the "how much the tracking
saw" section.

## After a session

1. `calibrate.bat` (once per camera position), then `analyze.bat` or the Colab route.
2. Double-click `coach.bat`. It writes the coach pack for the latest session.
3. Ask Claude: "review my last tennis session". Claude reads the pack and the
   picture strips and writes `review.md` into the same folder.
4. Double-click `coach.bat` again. It stores the review.

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

## Settings

`data\player.json`:

```json
{ "hand": "right", "backhand": "two", "height_cm": 180,
  "obsidian_file": "C:\\path\\to\\MyVault\\Sports.md" }
```

`obsidian_file` is optional; when present, each stored review is appended to it.
