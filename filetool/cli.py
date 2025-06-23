#!/usr/bin/env python3
# -*- coding: utf8 -*-
# tab-width:4

# pylint: disable=too-many-arguments              # [R0913] oo many arguments (13/10) [R0913]
# pylint: disable=too-many-positional-arguments   # [R0917] oo many positional arguments [R0917]
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive(!)

from __future__ import annotations

import sys
from pathlib import Path

import click

from .filetool import append_bytes_to_file


@click.group(
    context_settings={"show_default": True, "max_content_width": 272},
    no_args_is_help=True,
)
def cli() -> None:
    pass


def click_add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


CLICK_GLOBAL_OPTIONS = [
    click.option(
        "--path",
        required=True,
        type=click.Path(path_type=Path),
        help="Path to the file to write to.",
    ),
    click.option(
        "--do-not-create",
        "do_not_create_if_missing",
        is_flag=True,
        help="Do not create the file if missing.",
    ),
    click.option(
        "--make-parents",
        is_flag=True,
        help="Create parent directories if missing.",
    ),
    click.option(
        "--unlink-first",
        is_flag=True,
        help="Unlink (delete) the file before writing.",
    ),
    click.option(
        "--require-new",
        is_flag=True,
        help="Require that the file not already exist. (todo)",
    ),
    click.option(
        "--dry-run",
        is_flag=True,
        help="Simulate write: show what would be written, do not modify the file.",
    ),
]


@cli.command("append-line")
@click.argument("lines", type=str, nargs=-1)
@click_add_options(CLICK_GLOBAL_OPTIONS)
@click.option(
    "--unique",
    "unique_line",
    is_flag=True,
    help="Only write LINE if it is not already present in the file.",
)
@click.option(
    "--line-ending",
    "line_ending_code",
    help="Line ending. Defaults to `LF` (`0a` `\\n`). Also used to delineate lines for --unique comparison.",
    default="LF",
    type=click.Choice(["LF", "CRLF", "CR"]),
)
@click.option(
    "--comment-marker",
    help="Optional comment marker to use with --unique. Ignores comments when comparing.",
    default=None,
)
@click.option(
    "--ignore-leading-whitespace",
    is_flag=True,
    help="Ignore leading whitespace for the line matched by --unique.",
)
@click.option(
    "--ignore-trailing-whitespace",
    is_flag=True,
    help="Ignore trailing whitespace for the line matched by --unique.",
)
def _append_line_to_path(
    lines: tuple[str, ...],
    path: Path,
    unique_line: bool,
    do_not_create_if_missing: bool,
    make_parents: bool,
    unlink_first: bool,
    require_new: bool,
    dry_run: bool,
    line_ending_code: str,
    comment_marker: str,
    ignore_leading_whitespace: bool,
    ignore_trailing_whitespace: bool,
):
    """Append LINES to a file with control over creation, uniqueness, and error handling."""

    create_if_missing = not do_not_create_if_missing

    if not len(lines) > 0:
        raise click.ClickException("At least one LINE must be specified.")
    if unlink_first and not unique_line:
        raise click.ClickException("unlink_first=True requires unique_line=True.")
    if make_parents and not create_if_missing:
        raise click.ClickException(
            "create_if_missing=False requires make_parents=False."
        )

    if ignore_leading_whitespace:
        if not unique_line:
            raise click.ClickException("--ignore-leading-whitespace requires --unique.")

    if ignore_trailing_whitespace:
        if not unique_line:
            raise click.ClickException(
                "--ignore-trailing-whitespace requires --unique."
            )

    line_ending_dict = {
        "LF": b"\n",
        "CRLF": b"\r\n",
        "CR": b"\r",
    }
    try:
        line_ending = line_ending_dict[line_ending_code]
        bytes_payloads = []
        for _line in lines:
            if len(_line) == 0:
                raise click.ClickException(
                    "Error: cannot write empty input; please provide at least one byte."
                )
            _line_bytes = _line.encode("utf-8", errors="strict")  # latin1?
            assert line_ending not in _line_bytes

            # Append newline. Use `append-bytes` for more control.
            _line_bytes += line_ending
            bytes_payloads.append(_line_bytes)

        for _bytes in bytes_payloads:
            bytes_written = None
            if dry_run:
                click.echo(
                    f"[filetool append-line][dry-run] Would write: {_bytes!r} to {path}"
                )
                return

            bytes_written = append_bytes_to_file(
                bytes_payload=_bytes,
                path=path,
                unique_bytes=unique_line,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first,
                line_ending=line_ending if unique_line else None,
                comment_marker=(
                    comment_marker.encode("utf8") if comment_marker else None
                ),
                ignore_leading_whitespace=ignore_leading_whitespace,
                ignore_trailing_whitespace=ignore_trailing_whitespace,
            )
            if bytes_written:
                click.echo(
                    f"[filetool append-line] Wrote {len(_bytes)} bytes to {path}"
                )

    # except (OSError, ValueError) as e:
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command("append-bytes")
@click.argument("byte_vectors", type=str, nargs=-1)
@click_add_options(CLICK_GLOBAL_OPTIONS)
@click.option(
    "--unique",
    "unique_bytes",
    is_flag=True,
    help="Only write BYTES if it is not already present in the file.",
)
@click.option(
    "--hex-input",
    is_flag=True,
    help="Interpret input as hex (e.g., '68690a' -> b'hi\n').",
)
@click.option(
    "--bytes-from-path",
    type=click.Path(path_type=Path),
    help="Insert bytes from a file instead of LINE.",
)
def _append_bytes_to_path(
    byte_vectors: tuple[str, ...],
    path: Path,
    bytes_from_path: None | Path,
    unique_bytes: bool,
    do_not_create_if_missing: bool,
    make_parents: bool,
    unlink_first: bool,
    require_new: bool,
    hex_input: bool,
    dry_run: bool,
):
    """Append BYTES to a file with control over creation, uniqueness, and error handling."""

    create_if_missing = not do_not_create_if_missing
    if not (len(byte_vectors) > 0 or bytes_from_path):
        raise click.ClickException(
            "At least one of BYTES or --bytes-from-path must be specified."
        )
    if len(byte_vectors) > 0 and bytes_from_path:
        raise click.ClickException(
            "BYTES and --bytes-from-path are mutually exclusive."
        )
    if unlink_first and not unique_bytes:
        raise click.ClickException("unlink_first=True requires unique_bytes=True.")
    if make_parents and not create_if_missing:
        raise click.ClickException(
            "create_if_missing=False requires make_parents=False."
        )

    try:

        bytes_payloads = []
        if bytes_from_path:
            with open(bytes_from_path, "rb") as fh:
                bytes_payloads.append(fh.read())
        else:
            for _bv in byte_vectors:
                if len(_bv) == 0:
                    raise click.ClickException(
                        "Error: cannot write empty input; please provide at least one byte."
                    )
                if hex_input:
                    _line_bytes = bytes.fromhex(_bv)
                else:
                    _line_bytes = _bv.encode("utf-8", errors="strict")
                bytes_payloads.append(_line_bytes)

        for _bytes in bytes_payloads:
            bytes_written = None
            if dry_run:
                click.echo(f"[dry-run] Would write: {_bytes!r} to {path}")
                return

            bytes_written = append_bytes_to_file(
                bytes_payload=_bytes,
                path=path,
                unique_bytes=unique_bytes,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first,
            )
            if bytes_written:
                click.echo(f"[filetool] Wrote {len(_bytes)} bytes to {path}")

    except (OSError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    cli.main(args=sys.argv[1:], standalone_mode=True)
