"""Main CLI entrypoint for pyfoscam."""
from __future__ import annotations

import logging
import sys

import click

from .camera_cmd import (
    info_cmd,
    motion_cmd,
    preset_cmd,
    ptz_cmd,
    snapshot_cmd,
    status_cmd,
    stream_cmd,
)
from .config_cmd import config_group
from .media_cmd import media_group


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase output verbosity")
@click.option("-c", "--config", "config_path", help="Path to custom cameras.json config")
@click.pass_context
def cli(ctx: click.Context, verbose: int, config_path: str | None) -> None:
    """pyfoscam: Manage Foscam IP cameras and recording library."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
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
cli.add_command(preset_cmd)
cli.add_command(motion_cmd)


if __name__ == "__main__":
    cli()
