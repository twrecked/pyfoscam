"""CLI camera commands for pyfoscam."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click

from ..client import FoscamCamera
from ..config import get_camera_config
from ..const import DEFAULT_PTZ_TRAVEL_TIME, PTZ_COMMANDS
from .common import run_async

LOGGER = logging.getLogger(__package__)


def create_client_from_context(ctx: click.Context, name: str | None) -> tuple[str, FoscamCamera]:
    """Helper to instantiate FoscamCamera from CLI context."""
    cam_name, cfg = get_camera_config(
        name,
        config_path=ctx.obj.get("config_path"),
        hass_path=ctx.obj.get("hass_dir"),
    )
    verbose = ctx.obj.get("verbose", False)
    storage_dir = cfg.get("storage_dir")
    cam = FoscamCamera(
        host=cfg["host"],
        username=cfg["username"],
        password=cfg["password"],
        port=cfg.get("port", 88),
        rtsp_port=cfg.get("rtsp_port", 554),
        storage_dir=storage_dir,
        verbose=verbose,
    )
    return cam_name, cam


@click.command("status")
@click.argument("camera", required=False)
@click.pass_context
def status_cmd(ctx: click.Context, camera: str | None) -> None:
    """Show current camera sensors, controls, and recording status."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Querying status for '{cam_name}' ({client.host}:{client.port})...")
            full = await client.get_full_state()

            click.echo(
                f"  Motion Alarm:    {'ACTIVE' if full.get('motion_detected') else 'Clear'} (Enabled: {full.get('motion_enabled', False)})"
            )
            click.echo(
                f"  Sound Alarm:     {'ACTIVE' if full.get('sound_detected') else 'Clear'} (Enabled: {full.get('sound_enabled', False)})"
            )
            click.echo(
                f"  IO Alarm:        {'ACTIVE' if full.get('io_detected') else 'Clear'} (Enabled: {full.get('io_enabled', False)})"
            )
            click.echo(f"  Recording State: {'RECORDING' if full.get('is_recording') else 'Idle'}")

            if full.get("is_asleep") is not None:
                click.echo(f"  Privacy/Sleep:   {'ASLEEP' if full['is_asleep'] else 'Awake'}")
            if full.get("led_enabled") is not None:
                click.echo(f"  Status LED:      {'Enabled' if full['led_enabled'] else 'Disabled'}")
            if full.get("infra_led_mode") is not None:
                ir_str = "Auto" if full.get("infra_led_auto") else f"Manual (mode {full.get('infra_led_mode')})"
                click.echo(f"  Night Vision:    {ir_str}")
            if full.get("is_flip") is not None and full.get("is_mirror") is not None:
                flip_str = "On" if full["is_flip"] else "Off"
                mirror_str = "On" if full["is_mirror"] else "Off"
                click.echo(f"  Image Setting:   Flip: {flip_str}, Mirror: {mirror_str}")
            if full.get("volume") is not None:
                mute_str = f"Muted: {not full['voice_enabled']}" if full.get("voice_enabled") is not None else ""
                vol_str = f"{full['volume']}%" + (f" ({mute_str})" if mute_str else "")
                click.echo(f"  Speaker Volume:  {vol_str}")
            if full.get("white_light") is not None:
                wl = full["white_light"]
                click.echo(f"  White Light:     {'On' if wl.get('enable') == '1' else 'Off'}")
            if full.get("siren") is not None:
                siren = full["siren"]
                click.echo(f"  Siren Alarm:     {'ACTIVE' if siren.get('sirenEnable') == '1' else 'Off'}")

    run_async(_run())


@click.command("info")
@click.argument("camera", required=False)
@click.pass_context
def info_cmd(ctx: click.Context, camera: str | None) -> None:
    """Show camera hardware and firmware info."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Querying device info for '{cam_name}'...")
            info = await client.get_info()

            for k, v in sorted(info.items()):
                click.echo(f"  {k}: {v}")

    run_async(_run())


@click.command("snapshot")
@click.argument("camera", required=False)
@click.option("-o", "--output", default="snapshot.jpg", show_default=True, help="Output file path")
@click.pass_context
def snapshot_cmd(ctx: click.Context, camera: str | None, output: str) -> None:
    """Capture a snapshot and save as JPEG."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Taking snapshot from '{cam_name}'...")
            data = await client.get_snapshot()

        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(out_path.write_bytes, data)

        click.echo(f"Snapshot saved to: {out_path} ({len(data)} bytes)")

    run_async(_run())


@click.command("stream")
@click.argument("camera", required=False)
@click.option("--stream", default="Main", show_default=True, help="Main or Sub stream")
@click.pass_context
def stream_cmd(ctx: click.Context, camera: str | None, stream: str) -> None:
    """Display RTSP live stream URL."""
    cam_name, client = create_client_from_context(ctx, camera)
    url = client.rtsp_url(stream=stream)
    click.echo(f"Stream URL for '{cam_name}' [{stream}]:")
    click.echo(url)


@click.command("ptz")
@click.argument(
    "direction",
    type=click.Choice(list(PTZ_COMMANDS.keys()) + ["stop"], case_sensitive=False),
)
@click.argument("camera", required=False)
@click.option(
    "-t",
    "--travel-time",
    default=DEFAULT_PTZ_TRAVEL_TIME,
    show_default=True,
    type=float,
    help="Movement travel time (seconds)",
)
@click.pass_context
def ptz_cmd(ctx: click.Context, direction: str, camera: str | None, travel_time: float) -> None:
    """Move camera (up, down, left, right, top_left, etc)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            if direction.lower() == "stop":
                await client.ptz_stop()
                click.echo(f"Stopped movement on '{cam_name}'.")
            else:
                click.echo(f"Moving '{cam_name}' {direction} for {travel_time}s...")
                await client.ptz(direction, travel_time=travel_time)
                click.echo("Done.")

    run_async(_run())


@click.command("preset")
@click.argument("preset_name")
@click.argument("camera", required=False)
@click.pass_context
def preset_cmd(ctx: click.Context, preset_name: str, camera: str | None) -> None:
    """Move camera to a saved PTZ preset point."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Moving '{cam_name}' to preset '{preset_name}'...")
            await client.ptz_preset(preset_name)
            click.echo("Done.")

    run_async(_run())


@click.command("motion")
@click.argument("action", type=click.Choice(["enable", "disable"], case_sensitive=False))
@click.argument("camera", required=False)
@click.pass_context
def motion_cmd(ctx: click.Context, action: str, camera: str | None) -> None:
    """Enable or disable camera motion detection."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            if action.lower() == "enable":
                await client.enable_motion_detection()
                click.echo(f"Motion detection enabled on '{cam_name}'.")
            else:
                await client.disable_motion_detection()
                click.echo(f"Motion detection disabled on '{cam_name}'.")

    run_async(_run())


@click.command("sleep")
@click.argument("camera", required=False)
@click.pass_context
def sleep_cmd(ctx: click.Context, camera: str | None) -> None:
    """Put camera into sleep / privacy mode."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Putting '{cam_name}' to sleep...")
            await client.sleep()
            click.echo(f"'{cam_name}' is now asleep.")

    run_async(_run())


@click.command("wake")
@click.argument("camera", required=False)
@click.pass_context
def wake_cmd(ctx: click.Context, camera: str | None) -> None:
    """Wake camera from sleep / privacy mode."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Waking up '{cam_name}'...")
            await client.wake_up()
            click.echo(f"'{cam_name}' is now awake.")

    run_async(_run())


@click.command("led")
@click.argument("state", type=click.Choice(["on", "off", "status"], case_sensitive=False), default="status")
@click.argument("camera", required=False)
@click.pass_context
def led_cmd(ctx: click.Context, state: str, camera: str | None) -> None:
    """Get or set physical camera status LED (on/off/status)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            st = state.lower()
            if st == "status":
                enabled = await client.get_led_state()
                click.echo(f"Status LED on '{cam_name}': {'Enabled' if enabled else 'Disabled'}")
            else:
                enabled = st == "on"
                await client.set_led_state(enabled)
                click.echo(f"Status LED on '{cam_name}' set to: {'Enabled' if enabled else 'Disabled'}")

    run_async(_run())


@click.command("flip")
@click.argument("state", type=click.Choice(["on", "off", "status"], case_sensitive=False), default="status")
@click.argument("camera", required=False)
@click.pass_context
def flip_cmd(ctx: click.Context, state: str, camera: str | None) -> None:
    """Get or set vertical video flip (on/off/status)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            st = state.lower()
            if st == "status":
                mf = await client.get_flip_and_mirror()
                click.echo(f"Flip on '{cam_name}': {'On' if mf['is_flip'] else 'Off'}")
            else:
                flip = st == "on"
                await client.set_flip(flip)
                click.echo(f"Flip on '{cam_name}' set to: {'On' if flip else 'Off'}")

    run_async(_run())


@click.command("mirror")
@click.argument("state", type=click.Choice(["on", "off", "status"], case_sensitive=False), default="status")
@click.argument("camera", required=False)
@click.pass_context
def mirror_cmd(ctx: click.Context, state: str, camera: str | None) -> None:
    """Get or set horizontal video mirror (on/off/status)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            st = state.lower()
            if st == "status":
                mf = await client.get_flip_and_mirror()
                click.echo(f"Mirror on '{cam_name}': {'On' if mf['is_mirror'] else 'Off'}")
            else:
                mirror = st == "on"
                await client.set_mirror(mirror)
                click.echo(f"Mirror on '{cam_name}' set to: {'On' if mirror else 'Off'}")

    run_async(_run())


@click.command("ir")
@click.argument("mode", type=click.Choice(["auto", "on", "off", "status"], case_sensitive=False), default="status")
@click.argument("camera", required=False)
@click.pass_context
def ir_cmd(ctx: click.Context, mode: str, camera: str | None) -> None:
    """Get or set infrared / night vision mode (auto/on/off/status)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            m = mode.lower()
            if m == "status":
                cfg = await client.get_infra_led_config()
                auto = cfg.get("auto", False)
                click.echo(f"Night vision on '{cam_name}': {'Auto' if auto else f'Manual (mode {cfg.get("mode")})'}")
            else:
                await client.set_infra_led(m)
                click.echo(f"Night vision on '{cam_name}' set to: {m.capitalize()}")

    run_async(_run())


@click.command("volume")
@click.argument("level", required=False, type=click.IntRange(0, 100))
@click.argument("camera", required=False)
@click.pass_context
def volume_cmd(ctx: click.Context, level: int | None, camera: str | None) -> None:
    """Get or set speaker volume level (0-100)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            if level is None:
                vol = await client.get_volume()
                voice = await client.get_voice_state()
                mute_str = " (Muted)" if not voice else ""
                click.echo(f"Speaker volume for '{cam_name}': {vol}%{mute_str}")
            else:
                await client.set_volume(level)
                click.echo(f"Speaker volume for '{cam_name}' set to {level}%.")

    run_async(_run())


@click.command("mute")
@click.argument("action", type=click.Choice(["on", "off", "status"], case_sensitive=False), default="status")
@click.argument("camera", required=False)
@click.pass_context
def mute_cmd(ctx: click.Context, action: str, camera: str | None) -> None:
    """Mute or unmute speaker voice output (on/off/status)."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            act = action.lower()
            if act == "status":
                voice = await client.get_voice_state()
                click.echo(f"Audio mute on '{cam_name}': {'Muted' if not voice else 'Unmuted'}")
            elif act == "on":
                await client.set_voice_state(False)
                click.echo(f"Muted speaker audio on '{cam_name}'.")
            else:
                await client.set_voice_state(True)
                click.echo(f"Unmuted speaker audio on '{cam_name}'.")

    run_async(_run())
