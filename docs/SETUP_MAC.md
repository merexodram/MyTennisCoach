# Setup on a Mac (Apple Silicon)

Everything that runs on Windows runs on a Mac with an M-series chip. The
networks (court, ball, players, pose) use the Mac's GPU through Metal (MPS);
operations Metal lacks fall back to the CPU by themselves.

## Once

1. Install [Homebrew](https://brew.sh): paste its one-line install command
   into Terminal. If macOS asks to install the command line developer tools,
   accept.
2. Get the project into a folder of your choice: either clone it

   ```bash
   git clone --recurse-submodules --shallow-submodules https://github.com/merexodram/MyTennisCoach.git
   ```

   or let Claude copy it into a folder you connected.
3. Double-click `setup.command`. It installs Python 3.12 and ffmpeg with
   Homebrew, fetches the pinned upstream repositories, creates `.venv`,
   installs PyTorch and the other packages, downloads the weights and creates
   the database. The log is saved to `setup_log.txt`.

If macOS refuses to open a `.command` file ("cannot be opened because it is
from an unidentified developer"), right-click it, choose Open, and confirm
once. If it says the file is not executable, run `chmod +x *.command` in
Terminal in the project folder.

## Every session

| Windows | Mac | What it does |
|---|---|---|
| `calibrate.bat` | `calibrate.command` | click the court points and yourself, once per camera position |
| `analyze.bat` | `analyze.command` | analyse a recording |
| `prepare_colab.bat` | `prepare_colab.command` | working copy for the free Colab GPU (long recordings) |
| `coach.bat` | `coach.command` | coach pack, store the review, metrics, Obsidian notes, dashboard |
| `compare.bat` | `compare.command` | compare two sessions in Obsidian |
| `download.bat` | `download.command` | download the links in `data/links.txt` |

The Mac launchers open a Finder window to choose the video (drag and drop on
a `.command` file does not pass the file). A camera that splits a long
recording into parts (`VID_..._001.mp4`, `VID_..._002.mp4`): select all parts
together; they are joined into one file without re-encoding
(`VID_....mp4`, delete the parts afterwards if you like). The working copy is
made with the Mac's hardware video encoder; 4K at 120 fps becomes 1080p at
30 fps. The date of the session is read from the file name or the
recording's own creation time, not from when the file was copied. From Terminal, options work as on
Windows: `./analyze.command recording.mp4 --doubles`.

## Settings

`data/player.json` is the same as on Windows (see [COACH.md](COACH.md)). On a
Mac, Google Drive for desktop keeps the Drive under
`~/Library/CloudStorage/GoogleDrive-<account>/My Drive`; `~` and `*` are
allowed in `obsidian_dir`:

```json
{ "obsidian_dir": "~/Library/CloudStorage/GoogleDrive-*/My Drive/MyVault/Tennis" }
```

## Speed

Not measured on a Mac yet. The analysis prints the time per frame; for long
recordings the Colab route (docs/COLAB.md) stays available.
