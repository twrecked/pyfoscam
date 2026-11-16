# pyfoscam

A Python library and CLI for managing Foscam IP cameras, accessing camera state, and discovering, downloading, and converting local SD-card video recordings and snapshots.

## Features
- **Device state & telemetry**: Query motion, sound, IO alarm states, and recording status.
- **PTZ & controls**: Pan/tilt/zoom, preset navigation, and live snapshot capture.
- **Media management**: Discovers recordings (`.avi`) and snapshots (`.jpg`) stored on the camera's local storage via its built-in FTP server.
- **Remuxing & transcoding**: Fast stream-copy remuxing from `.avi` to `.mp4` using `ffmpeg`.
- **CLI tool (`foscam`)**: Command-line tool to manage camera credentials, check status, trigger PTZ, capture snapshots, and browse/download video recordings.

## CLI Usage

```bash
# Add camera configuration
foscam config add living_room --host 192.168.1.50 --port 88 --user admin --pwd secret

# Query camera status
foscam status living_room

# Take a snapshot
foscam snapshot living_room -o snap.jpg

# Pan / Tilt
foscam ptz living_room up --travel-time 0.2

# List recordings
foscam media list living_room --days 7

# Download recording
foscam media download living_room MD20210522_120400 -o clip.mp4
```
