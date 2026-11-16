# pyfoscam

A Python library and CLI for managing Foscam IP cameras, accessing camera state, and discovering, downloading, and converting local SD-card video recordings and snapshots.

## Features
- **Device state & telemetry**: Query motion, sound, IO alarm states, and recording status.
- **PTZ & controls**: Pan/tilt/zoom, preset navigation, and live snapshot capture.
- **Media management**: Discovers recordings (`.avi`) and snapshots (`.jpg`) stored on the camera's local storage via its built-in FTP server.
- **Remuxing & transcoding**: Fast stream-copy remuxing from `.avi` to `.mp4` using `ffmpeg`.
- **CLI tool (`pyfoscam`)**: Command-line tool to manage camera credentials, check status, trigger PTZ, capture snapshots, and browse/download video recordings.

## CLI Usage

```bash
# Add camera configuration
pyfoscam config add living_room --host 192.168.1.50 --port 88 --user admin --pwd secret

# Query camera status
pyfoscam status living_room

# Take a snapshot
pyfoscam snapshot living_room -o snap.jpg

# Pan / Tilt
pyfoscam ptz living_room up --travel-time 0.2

# List recordings
pyfoscam media list living_room --days 7

# Download recording
pyfoscam media download living_room MD20210522_120400 -o clip.mp4

# Using Home Assistant configuration (--hass)
# Auto-detects HA config entries in /config, ~/.homeassistant, or sites:
pyfoscam --hass status
pyfoscam --hass media list
# Or specify HA config path directly:
pyfoscam --hass /home/user/homeassistant media list
```
