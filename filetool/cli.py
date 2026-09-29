#!/usr/bin/env python3
# tab-width:4

# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-positional-arguments   # [R0917]

from __future__ import annotations

import sys
from collections.abc import Callable
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click

from .append_bytes_to_file import append_bytes_to_file
from .append_line_to_file import append_line_to_file
from .validation import ValidationError

LINE_ENDINGS = {
    "LF": b"\n",
    "CRLF": b"\r\n",
    "CR": b"\r",
}


@click.group(
    context_settings={"show_default": True, "max_content_width": 272},
    no_args_is_help=True,
)
def cli() -> None:
    pass


Decorator = Callable[[Callable[..., Any]], Callable[..., Any]]


def click_add_options(options: Sequence[Decorator]) -> Decorator:
    def _add_options(func: Callable[..., Any]) -> Callable[..., Any]:
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
        help="Unlink (delete) the file before writing the first payload.",
    ),
]


@cli.command("append-line")
@click.argument(
    "lines",
    type=str,
    nargs=-1,
)
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
    help="Line ending. Also used to delineate lines for --unique comparison.",
    default="LF",
    type=click.Choice(list(LINE_ENDINGS)),
)
@click.option(
    "--comment-marker",
    help="Comment marker to strip before --unique comparison.",
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
def append_line_command(
    lines: tuple[str, ...],
    path: Path,
    unique_line: bool,
    do_not_create_if_missing: bool,
    make_parents: bool,
    unlink_first: bool,
    line_ending_code: str,
    comment_marker: str | None,
    ignore_leading_whitespace: bool,
    ignore_trailing_whitespace: bool,
) -> None:
    """Append LINES to a file with control over creation, uniqueness, and error handling."""

    if not len(lines) > 0:
        raise click.ClickException("At least one LINE must be specified.")

    line_ending = LINE_ENDINGS[line_ending_code]
    create_if_missing = not do_not_create_if_missing

    for index, line in enumerate(lines):
        try:
            bytes_written = append_line_to_file(
                line=line,
                path=path,
                unique=unique_line,
                line_ending=line_ending,
                comment_marker=comment_marker,
                ignore_leading_whitespace=ignore_leading_whitespace,
                ignore_trailing_whitespace=ignore_trailing_whitespace,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first and index == 0,
            )
        except ValidationError as e:
            raise click.ClickException(e.cli_msg or str(e)) from e

        if bytes_written:
            click.echo(f"[filetool] Wrote {bytes_written} bytes to {path}")


@cli.command("append-bytes")
@click.argument(
    "byte_vectors",
    type=str,
    nargs=-1,
)
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
    help="Interpret input as hex (e.g., '68690a' -> b'hi\\n').",
)
@click.option(
    "--bytes-from-path",
    type=click.Path(path_type=Path),
    help="Insert bytes from a file instead of positional args.",
)
def append_bytes_command(
    byte_vectors: tuple[str, ...],
    path: Path,
    bytes_from_path: Path | None,
    unique_bytes: bool,
    do_not_create_if_missing: bool,
    make_parents: bool,
    unlink_first: bool,
    hex_input: bool,
) -> None:
    """Append BYTES to a file with control over creation, uniqueness, and error handling."""

    if not (len(byte_vectors) > 0 or bytes_from_path):
        raise click.ClickException(
            "At least one of BYTES or --bytes-from-path must be specified."
        )
    if len(byte_vectors) > 0 and bytes_from_path:
        raise click.ClickException(
            "BYTES and --bytes-from-path are mutually exclusive."
        )

    create_if_missing = not do_not_create_if_missing

    bytes_payloads: list[bytes] = []
    if bytes_from_path:
        bytes_payloads.append(bytes_from_path.read_bytes())
    else:
        for bv in byte_vectors:
            if len(bv) == 0:
                raise click.ClickException("Cannot write empty input")
            if hex_input:
                try:
                    bytes_payloads.append(bytes.fromhex(bv))
                except ValueError as e:
                    raise click.ClickException(f"Invalid hex input: {e}") from e
            else:
                bytes_payloads.append(bv.encode("utf-8", errors="strict"))

    for index, data in enumerate(bytes_payloads):
        try:
            bytes_written = append_bytes_to_file(
                data=data,
                path=path,
                unique=unique_bytes,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first and index == 0,
            )
        except ValidationError as e:
            raise click.ClickException(e.cli_msg or str(e)) from e

        if bytes_written:
            click.echo(f"[filetool] Wrote {bytes_written} bytes to {path}")


if __name__ == "__main__":
    cli.main(args=sys.argv[1:], standalone_mode=True)
