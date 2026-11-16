"""CLI camera commands for pyfoscam."""
from __future__ import annotations

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
    """Show current camera sensor and recording status."""

    async def _run() -> None:
        cam_name, client = create_client_from_context(ctx, camera)
        async with client:
            click.echo(f"Querying status for '{cam_name}' ({client.host}:{client.port})...")
            state = await client.get_state()

            click.echo(
                f"  Motion Alarm:    {'ACTIVE' if state['motion_detected'] else 'Clear'} (Enabled: {state['motion_enabled']})"
            )
            click.echo(
                f"  Sound Alarm:     {'ACTIVE' if state['sound_detected'] else 'Clear'} (Enabled: {state['sound_enabled']})"
            )
            click.echo(
                f"  IO Alarm:        {'ACTIVE' if state['io_detected'] else 'Clear'} (Enabled: {state['io_enabled']})"
            )
            click.echo(f"  Recording State: {'RECORDING' if state['is_recording'] else 'Idle'}")

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
        with open(out_path, "wb") as f:
            f.write(data)

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
