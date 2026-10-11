# Tracking on a free Colab GPU

A 4 GB laptop GPU needs about 0.25 s per frame for each run of the ball
network, which makes a two-hour session an overnight job. A free Colab T4 GPU
should be several times faster. Only the tracking pass moves to the cloud;
everything else stays at home.

Status: the notebook has not been run on Colab yet. The `--track-only` path it
uses is tested locally.

## Steps

| Where | What |
|---|---|
| Home | Camera of your own: drag the recording onto `calibrate.bat` once (court points, then click on yourself). |
| Home | Drag the recording onto `prepare_colab.bat`. It makes the 1080p working copy and fills `outputs\for_colab`. |
| Browser | Upload the contents of `outputs\for_colab` to Google Drive: `My Drive/MyTennisCoach/in`. |
| Browser | Open `notebooks/track_on_colab.ipynb` in Colab (File > Open notebook > GitHub > `merexodram/MyTennisCoach`), set the runtime to T4 GPU, Run all. |
| Browser | Download `*_tracks.pkl` from `My Drive/MyTennisCoach/out`. |
| Home | Put them in `F:\MyTennisCoach\outputs\cache`, then drag the recording onto `analyze.bat`. With the tracks present it takes about a minute. |

## Sizes and limits

- A 1080p / 30 fps working copy is roughly 1 to 2 GB per hour, so a two-hour
  session is a 2 to 4 GB upload. The 4K original never leaves the laptop.
- Free Colab sessions stop after some hours or when idle. The tracking saves
  its progress every two minutes; running the cell again resumes.
- The footage is uploaded to your own Google Drive and processed on a Google
  machine. Keep that in mind for recordings with other people in them.
