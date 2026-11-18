# 🚀 pyfoscam v0.1.0-alpha.2 — Hardware Controls & CLI Enhancements

> ### ⚠️ Alpha Release Notice
> **pyfoscam is an async-first library and CLI for managing Foscam IP cameras and local SD-card storage over CGI and FTP.**
>
> Feedback and testing are welcome! If you encounter unhandled responses or connection issues, please report them on [GitHub Issues](https://github.com/twrecked/pyfoscam/issues).

---

## 🌟 Highlights

### 1. Native Async Hardware Controls (`foscam.client`)
Added native coroutines on `FoscamCamera` for comprehensive hardware management over CGI:
- **Sleep / Privacy Mode:** `is_asleep()`, `sleep()`, `wake_up()` (`getAlexaState`, `alexaSleep`, `alexaWakeUp`).
- **Physical Status LED:** `get_led_state()`, `set_led_state(enabled)` (`getLedEnableState`, `setLedEnableState`).
- **Image Orientation:** `get_flip_and_mirror()`, `set_flip(flip)`, `set_mirror(mirror)` (`getMirrorAndFlipSetting`, `flipVideo`, `mirrorVideo`).
- **Infrared Night Vision:** `get_infra_led_config()`, `set_infra_led_config(mode)`, `open_infra_led()`, `close_infra_led()`, `set_infra_led(mode_or_state)` (`getInfraLedConfig`, `setInfraLedConfig`, `openInfraLed`, `closeInfraLed`).
- **Audio & Volume:** `get_volume()`, `set_volume(volume)`, `get_voice_state()`, `set_voice_state(enabled)`, `get_speak_volume()`, `set_speak_volume(volume)` (`getAudioVolume`, `setAudioVolume`, `getVoiceEnableState`, `setVoiceEnableState`).
- **White Light & Siren (Model-Dependent):** `open_white_light()`, `close_white_light()`, `get_white_light_brightness()`, `get_siren_config()`, `set_siren_config(enable, volume)`.
- **Unified Telemetry:** `get_full_state()` queries all sensor alarms and hardware control states concurrently with `asyncio.gather(..., return_exceptions=True)`, safely returning `None` for endpoints not supported by specific camera hardware.

### 2. Comprehensive CLI Status & New Control Commands
- **Enriched `status` Output:** Reports alarm states alongside privacy/sleep, status LED, night vision mode, flip/mirror orientation, volume, and mute status:
  ```text
  $ pyfoscam --hass status
  Querying status for 'Back Garden' (192.168.1.100:88)...
    Motion Alarm:    Clear (Enabled: True)
    Sound Alarm:     Clear (Enabled: False)
    IO Alarm:        Clear (Enabled: False)
    Recording State: Idle
    Privacy/Sleep:   Awake
    Status LED:      Enabled
    Night Vision:    Auto
    Image Setting:   Flip: Off, Mirror: Off
    Speaker Volume:  100% (Muted: False)
  ```
- **New Control Commands:** Direct CLI control for camera features:
  - `pyfoscam sleep` / `pyfoscam wake`
  - `pyfoscam led [on|off|status]`
  - `pyfoscam volume [0-100]`
  - `pyfoscam mute [on|off|status]`
  - `pyfoscam ir [auto|on|off|status]`
  - `pyfoscam flip [on|off|status]`
  - `pyfoscam mirror [on|off|status]`

### 3. Refactored Home Assistant CLI Options (`--hass` & `--hass-dir`)
- Split `--hass` into a pure boolean flag (looking for Home Assistant configuration in standard locations: `/config`, `$HASS_DIR`, `~/.homeassistant`, `~/ha/sites/*/home-assistant`).
- Added an explicit `--hass-dir <DIR>` argument for directly targeting custom or bind-mounted Home Assistant directories.
- Removed custom `argv` preprocessing workarounds, standardizing Click option parsing.

### 4. Test Suite Expansion
- Added unit tests for all new coroutines in `tests/test_client.py` and CLI options in `tests/test_config.py`.
- Full test suite now contains 25 passing unit tests.
