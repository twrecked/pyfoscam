"""Main CLI entrypoint for pyfoscam."""
from __future__ import annotations

import logging

import click

from .camera_cmd import (
    flip_cmd,
    focus_cmd,
    info_cmd,
    ir_cmd,
    led_cmd,
    mirror_cmd,
    motion_cmd,
    mute_cmd,
    preset_cmd,
    ptz_cmd,
    sleep_cmd,
    snapshot_cmd,
    status_cmd,
    stream_cmd,
    volume_cmd,
    wake_cmd,
    zoom_cmd,
)
from .config_cmd import config_group
from .media_cmd import media_group


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase output verbosity")
@click.option("-c", "--config", "config_path", help="Path to custom cameras.json config")
@click.option("--hass", is_flag=True, default=False, help="Use Home Assistant configuration from standard locations")
@click.option("--hass-dir", default=None, help="Path to Home Assistant configuration directory (implies --hass)")
@click.pass_context
def cli(ctx: click.Context, verbose: int, config_path: str | None, hass: bool, hass_dir: str | None) -> None:
    """pyfoscam: Manage Foscam IP cameras and recording library."""
    ctx.ensure_object(dict)
    target_hass: str | None = None
    if hass_dir:
        target_hass = hass_dir
    elif hass:
        target_hass = "__AUTO__"

    ctx.obj["config_path"] = config_path
    ctx.obj["hass_dir"] = target_hass
    ctx.obj["verbose"] = verbose > 0

    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# Register groups and commands
cli.add_command(config_group)
cli.add_command(media_group)
cli.add_command(status_cmd)
cli.add_command(info_cmd)
cli.add_command(snapshot_cmd)
cli.add_command(stream_cmd)
cli.add_command(ptz_cmd)
cli.add_command(zoom_cmd)
cli.add_command(focus_cmd)
cli.add_command(preset_cmd)
cli.add_command(motion_cmd)
cli.add_command(sleep_cmd)
cli.add_command(wake_cmd)
cli.add_command(led_cmd)
cli.add_command(flip_cmd)
cli.add_command(mirror_cmd)
cli.add_command(ir_cmd)
cli.add_command(volume_cmd)
cli.add_command(mute_cmd)


def main() -> None:
    cli.main()


if __name__ == "__main__":
    main()
