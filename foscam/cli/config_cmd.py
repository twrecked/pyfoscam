"""CLI config commands for pyfoscam."""
from __future__ import annotations

import click

from ..config import (
    get_camera_config,
    get_default_config_path,
    load_config,
    remove_camera_config,
    save_config,
    set_camera_config,
)
from ..const import DEFAULT_PORT, DEFAULT_RTSP_PORT


@click.group("config")
def config_group() -> None:
    """Manage camera configurations and credentials."""


@config_group.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """List all configured cameras."""
    conf = load_config(ctx.obj.get("config_path"))
    cameras = conf.get("cameras", {})
    default_cam = conf.get("default")

    if not cameras:
        click.echo("No cameras configured yet. Use 'pyfoscam config add' to add one.")
        return

    click.echo(f"Config file: {ctx.obj.get('config_path') or get_default_config_path()}")
    click.echo(f"Default camera: {default_cam or 'None'}\n")
    click.echo(f"{'Camera Name':<20} {'Host':<20} {'HTTP':<8} {'RTSP':<8} {'User':<15}")
    click.echo("-" * 75)
    for name, c in cameras.items():
        is_def = " *" if name == default_cam else ""
        click.echo(
            f"{name + is_def:<20} {c.get('host', ''):<20} {c.get('port', 88):<8} "
            f"{c.get('rtsp_port', 554):<8} {c.get('username', ''):<15}"
        )


@config_group.command("add")
@click.argument("name")
@click.option("--host", required=True, help="Camera IP address or hostname")
@click.option("--user", "--username", "username", required=True, help="Camera username")
@click.option("--pwd", "--password", "password", required=True, help="Camera password")
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int, help="Camera HTTP port")
@click.option("--rtsp-port", default=DEFAULT_RTSP_PORT, show_default=True, type=int, help="Camera RTSP port")
@click.option("--default", "is_default", is_flag=True, help="Set as default camera")
@click.pass_context
def config_add(
    ctx: click.Context,
    name: str,
    host: str,
    username: str,
    password: str,
    port: int,
    rtsp_port: int,
    is_default: bool,
) -> None:
    """Add or update camera configuration."""
    set_camera_config(
        name=name,
        host=host,
        username=username,
        password=password,
        port=port,
        rtsp_port=rtsp_port,
        is_default=is_default,
        config_path=ctx.obj.get("config_path"),
    )
    click.echo(f"Saved configuration for camera '{name}'.")


@config_group.command("remove")
@click.argument("name")
@click.pass_context
def config_remove(ctx: click.Context, name: str) -> None:
    """Remove a camera configuration."""
    removed = remove_camera_config(name, config_path=ctx.obj.get("config_path"))
    if removed:
        click.echo(f"Removed camera '{name}'.")
    else:
        click.echo(f"Camera '{name}' not found.")


@config_group.command("set-default")
@click.argument("name")
@click.pass_context
def config_set_default(ctx: click.Context, name: str) -> None:
    """Set the default camera."""
    conf = load_config(ctx.obj.get("config_path"))
    cameras = conf.get("cameras", {})
    if name not in cameras:
        raise click.ClickException(f"Camera '{name}' does not exist.")
    conf["default"] = name
    save_config(conf, ctx.obj.get("config_path"))
    click.echo(f"Default camera set to '{name}'.")


@config_group.command("show")
@click.argument("name", required=False)
@click.pass_context
def config_show(ctx: click.Context, name: str | None) -> None:
    """Show details for a specific camera."""
    cam_name, cam_cfg = get_camera_config(name, ctx.obj.get("config_path"))
    click.echo(f"Camera: {cam_name}")
    for k, v in cam_cfg.items():
        val = "********" if k == "password" else v
        click.echo(f"  {k}: {val}")
