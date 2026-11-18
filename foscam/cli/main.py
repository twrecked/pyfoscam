"""Main CLI entrypoint for pyfoscam."""
from __future__ import annotations

import logging
import sys

import click

from .camera_cmd import (
    flip_cmd,
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
)
from .config_cmd import config_group
from .media_cmd import media_group


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase output verbosity")
@click.option("-c", "--config", "config_path", help="Path to custom cameras.json config")
@click.option("--hass", "hass_dir", is_flag=False, flag_value="/config", default=None, help="Use Home Assistant configuration and camera entries (defaults to /config, or specify path)")
@click.pass_context
def cli(ctx: click.Context, verbose: int, config_path: str | None, hass_dir: str | None) -> None:
    """pyfoscam: Manage Foscam IP cameras and recording library."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["hass_dir"] = hass_dir
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
cli.add_command(sleep_cmd)
cli.add_command(wake_cmd)
cli.add_command(led_cmd)
cli.add_command(flip_cmd)
cli.add_command(mirror_cmd)
cli.add_command(ir_cmd)
cli.add_command(volume_cmd)
cli.add_command(mute_cmd)


KNOWN_SUBCOMMANDS = {
    "config",
    "media",
    "status",
    "info",
    "snapshot",
    "stream",
    "ptz",
    "preset",
    "motion",
    "sleep",
    "wake",
    "led",
    "flip",
    "mirror",
    "ir",
    "volume",
    "mute",
}


def preprocess_argv(args: list[str]) -> list[str]:
    """Preprocess arguments so '--hass' without path defaults to auto-detect."""
    new_args = list(args)
    for i, arg in enumerate(new_args):
        if arg == "--hass" and (
            i + 1 >= len(new_args)
            or new_args[i + 1].startswith("-")
            or new_args[i + 1] in KNOWN_SUBCOMMANDS
        ):
            new_args[i] = "--hass=__AUTO__"
    return new_args


def main() -> None:
    args = preprocess_argv(sys.argv[1:])
    cli.main(args=args)


if __name__ == "__main__":
    main()
