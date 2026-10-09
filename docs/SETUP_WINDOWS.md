# Windows setup

## 1. Prerequisites

| Tool | Version | Install |
|---|---|---|
| NVIDIA driver | current | GeForce Experience or nvidia.com. Check with `nvidia-smi` |
| Git | any recent | `winget install Git.Git` |
| Python | 3.11 | `winget install Python.Python.3.11` |
| ffmpeg | any recent | `winget install Gyan.FFmpeg` |

Open a new PowerShell window after installing so PATH is refreshed.

An NVIDIA GPU with 8 GB of memory or more is the practical minimum for full
matches. Phase 0 clips of 30 seconds also run on CPU, slowly.

## 2. Get the project

```powershell
git clone --recurse-submodules --shallow-submodules https://github.com/merexodram/MyTennisCoach.git F:\MyTennisCoach
cd F:\MyTennisCoach
```

If the folder was cloned without submodules: `git submodule update --init --depth 1`.

## 3. Run the setup script

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

It checks the tools, fetches the upstream repositories, creates `.venv`,
installs PyTorch and the other packages, downloads the pretrained weights and
creates `data\tennis.duckdb`.

Options:

- `-Cuda cu124` for newer drivers, `-Cuda cpu` for a machine without an NVIDIA GPU.

The last line printed should be `CUDA available: True`.

## 4. Daily use

```powershell
cd F:\MyTennisCoach
.\.venv\Scripts\Activate.ps1
```

## Disk use

| Item | Size |
|---|---|
| Python environment with PyTorch | about 6 GB |
| Upstream repositories (shallow) | about 0.6 GB |
| Weights | about 0.5 GB |
| A 30 s test clip at 720p | about 10 MB |
| One hour of 4K/60 action-cam footage | 25 to 50 GB before trimming |
