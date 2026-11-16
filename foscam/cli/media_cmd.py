"""CLI media commands for pyfoscam."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from .camera_cmd import create_client_from_context

LOGGER = logging.getLogger(__package__)


def format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num_bytes} B"


@click.group("media")
def media_group() -> None:
    """Browse and download video recordings and snapshots from camera."""


@media_group.command("list")
@click.argument("camera", required=False)
@click.option("--days", default=15, show_default=True, type=int, help="Days of history to search")
@click.option("--limit", default=25, show_default=True, type=int, help="Maximum recordings to display")
@click.pass_context
def media_list(ctx: click.Context, camera: str | None, days: int, limit: int) -> None:
    """List recordings discovered on camera storage."""
    cam_name, client = create_client_from_context(ctx, camera)
    client.media.days_cutoff = days

    click.echo(f"Scanning media on '{cam_name}' (last {days} days)...")
    recordings = client.media.refresh()

    if not recordings:
        click.echo("No recordings found.")
        return

    click.echo(
        f"Found {len(recordings)} recordings (Today: {client.media.captured_today}). "
        f"Showing newest {min(limit, len(recordings))}:\n"
    )
    click.echo(f"{'Clip ID':<26} {'Date/Time':<18} {'Trigger':<10} {'Size':<10} {'Downloaded':<10}")
    click.echo("-" * 78)

    for rec in recordings[:limit]:
        down_status = "YES (MP4)" if rec.is_downloaded else ("YES (AVI)" if rec.is_raw_downloaded else "No")
        click.echo(
            f"{rec.clip_id:<26} {rec.created_at_pretty():<18} {rec.trigger:<10} "
            f"{format_bytes(rec.remote_size):<10} {down_status:<10}"
        )


@media_group.command("download")
@click.argument("clip_id")
@click.argument("camera", required=False)
@click.option("-o", "--output", help="Destination file path for video")
@click.option("--raw", is_flag=True, help="Download raw AVI without converting to MP4")
@click.option("--force", is_flag=True, help="Re-download even if already present locally")
@click.pass_context
def media_download(
    ctx: click.Context,
    clip_id: str,
    camera: str | None,
    output: str | None,
    raw: bool,
    force: bool,
) -> None:
    """Download a specific recording clip by its Clip ID."""
    cam_name, client = create_client_from_context(ctx, camera)
    click.echo(f"Refreshing media catalog on '{cam_name}'...")
    client.media.refresh()

    rec = client.media.get_recording(clip_id)
    if not rec:
        raise click.ClickException(f"Clip '{clip_id}' not found on camera '{cam_name}'.")

    click.echo(f"Downloading clip {clip_id} ({format_bytes(rec.remote_size)})...")
    dest_path = Path(output) if output else None

    vid_path, snap_path = client.media.download_recording(
        rec,
        dest_video=dest_path,
        remux_to_mp4=not raw,
        force=force,
    )

    click.echo(f"Video saved to: {vid_path}")
    if snap_path and snap_path.is_file():
        click.echo(f"Thumbnail saved to: {snap_path}")


@media_group.command("sync")
@click.argument("camera", required=False)
@click.option("--days", default=1, show_default=True, type=int, help="Days of recordings to sync")
@click.option("--limit", default=5, show_default=True, type=int, help="Max new recordings to download")
@click.option("--raw", is_flag=True, help="Skip MP4 remuxing")
@click.pass_context
def media_sync(
    ctx: click.Context,
    camera: str | None,
    days: int,
    limit: int,
    raw: bool,
) -> None:
    """Download the most recent undownloaded recordings."""
    cam_name, client = create_client_from_context(ctx, camera)
    client.media.days_cutoff = days

    click.echo(f"Refreshing media catalog on '{cam_name}'...")
    recordings = client.media.refresh()

    needed = [r for r in recordings if not r.is_downloaded and not r.is_raw_downloaded][:limit]
    if not needed:
        click.echo("All recordings within window are already downloaded.")
        return

    click.echo(f"Downloading {len(needed)} new recordings...")
    for rec in needed:
        try:
            click.echo(f"  Downloading {rec.clip_id} ({rec.created_at_pretty()})...")
            vid_path, _ = client.media.download_recording(rec, remux_to_mp4=not raw)
            click.echo(f"    Saved: {vid_path}")
        except Exception as err:
            click.echo(f"    Failed: {err}", err=True)

    click.echo("Sync complete.")
