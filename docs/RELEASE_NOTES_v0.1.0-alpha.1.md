# 🚀 pyfoscam v0.1.0-alpha.1 — Asynchronous Python Library & CLI for Foscam IP Cameras

> ### ⚠️ Alpha Release & Community Testing Notice
> **pyfoscam is an async-first library and CLI for managing Foscam IP cameras and local SD-card storage over CGI and FTP.**
>
> This is the initial alpha release. While the core architecture is non-blocking and tested with modern Foscam hardware, firmware implementations across different Foscam models can vary.
>
> **Feedback and testing are welcome!** If you encounter unhandled responses or connection issues, please report them on [GitHub Issues](https://github.com/twrecked/pyfoscam/issues).

---

## 🌟 Highlights

### 1. Native `asyncio` Core (Python >= 3.10)
- **Direct CGI Communication (`foscam.client`):** Connects asynchronously directly to the camera's `/cgi-bin/CGIProxy.fcgi` endpoint using `aiohttp.ClientSession`, eliminating unmaintained legacy third-party dependencies.
- **In-Memory XML Parsing:** Parses camera responses with standard library `xml.etree.ElementTree` and maps camera error codes to typed exceptions (`FoscamConnectionError`, `FoscamAuthError`, `FoscamCommandError`).
- **Async Hardware Controls:** Native coroutines for `get_state()`, `get_info()`, `get_snapshot()`, `enable_motion_detection()`, `disable_motion_detection()`, `ptz()`, `ptz_stop()`, `ptz_preset()`, and `get_ptz_presets()`.
- **Zero Event Loop Blocking:** Replaced all blocking sleeps with `asyncio.sleep()`.

### 2. Camera Storage & Persistent Caching (`foscam.ftp`, `foscam.media`)
- **Non-Blocking FTP Client:** Camera FTP operations (port 50021) are safely offloaded to worker threads via `asyncio.to_thread` with an async mutex lock.
- **Persistent Disk Caching:** Caches historical SD card recording metadata into `.cache_<camera_id>.json`. On subsequent refreshes, the FTP engine skips historical dates and queries only today's active folder, slashing refresh times from ~30+ seconds down to under 1 second.
- **Sliding Window Pruning:** Automatically evicts cached records older than `days_cutoff` (default 15 days).

### 3. Non-Blocking Transcoding & Media Pruning
- **Subprocess Transcoding (`foscam.transcode`):** Uses `asyncio.create_subprocess_exec` to run fast lossless remuxing (`ffmpeg -c copy -movflags +faststart`) and ffprobe duration detection without thread or loop stalls.
- **Local Storage Retention (`prune_local_recordings`):** Automatically scans and unlinks local `.mp4`, `.avi`, and `.jpg` downloads older than a configured retention threshold.

### 4. Comprehensive Command-Line Interface (`pyfoscam`)
- **Camera Commands:** `config`, `status`, `info`, `snapshot`, `stream`, `ptz`, `preset`, `motion`.
- **Media Commands:** `media list`, `media download`, `media sync`, `media prune`, `media clear-cache`.
- **Home Assistant Auto-Detection:** Global `--hass` flag automatically reads camera credentials directly from Home Assistant's `core.config_entries`.

### 5. Type Safety & Standards
- Includes PEP 561 `py.typed` marker file.
- Full type annotations passing `mypy` with 0 issues.
- Code style adheres strictly to PEP 8, formatted and linted with `ruff`.
- 17 automated unit tests (`pytest pyfoscam/tests/`).
