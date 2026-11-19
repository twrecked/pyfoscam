# 🚀 pyfoscam v0.1.0-alpha.3 — Optical Zoom & Manual Focus Lens Controls

> ### ⚠️ Alpha Release Notice
> **pyfoscam is an async-first library and CLI for managing Foscam IP cameras and local SD-card storage over CGI and FTP.**
>
> Feedback and testing are welcome! If you encounter unhandled responses or connection issues, please report them on [GitHub Issues](https://github.com/twrecked/pyfoscam/issues).

---

## 🌟 Highlights

### 1. Optical Zoom & Manual Focus Controls (`foscam.client`)
Added native coroutines on `FoscamCamera` for motorized optical zoom and manual lens focus:
- **Optical Zoom:** `zoom(direction="in"|"out", travel_time=0.125)` and `zoom_stop()` (`zoomIn`, `zoomOut`, `zoomStop`).
- **Manual Lens Focus:** `focus(direction="near"|"far", travel_time=0.125)` and `focus_stop()` (`focusNear`, `focusFar`, `focusStop`).
- **Cancellation Safety:** Implemented `try ... finally` guarantees across all timed travel actions (`ptz`, `zoom`, `focus`) so that stop commands are reliably transmitted to the camera even if an asyncio task is cancelled.

### 2. New CLI Commands
Direct CLI commands for controlling lens zoom and focus:
- `pyfoscam zoom in` / `pyfoscam zoom out` / `pyfoscam zoom stop` (with optional `--travel-time` / `-t`)
- `pyfoscam focus near` / `pyfoscam focus far` / `pyfoscam focus stop` (with optional `--travel-time` / `-t`)

### 3. Test Suite Expansion
- Added unit tests for `zoom`, `zoom_stop`, `focus`, and `focus_stop` with travel time and invalid argument handling in `tests/test_client.py`.
- Verified against physical camera hardware (FI9928P+V2).
