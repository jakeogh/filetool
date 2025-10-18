#!/usr/bin/env python3
# tab-width:4

# pylint: disable=too-many-arguments              # [R0913] oo many arguments (13/10) [R0913]
# pylint: disable=too-many-positional-arguments   # [R0917] oo many positional arguments [R0917]
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive(!)

from __future__ import annotations

import sys
from pathlib import Path

import click

from .filetool import append_bytes_to_file

# =============================================================================
# Custom exception for validation with CLI-friendly messages
# =============================================================================


class ValidationError(ValueError):
    """
    Validation error that can carry both Python API and CLI-friendly messages.

    When raised from standalone functions, can include a CLI-specific message
    that references flag names instead of parameter names.
    """

    def __init__(
        self,
        msg: str,
        cli_msg: str | None = None,
    ):
        super().__init__(msg)
        self.cli_msg = cli_msg


# =============================================================================
# Standalone functions (can be called from Python or CLI)
# =============================================================================


def append_line(
    *,
    line: str,
    path: Path,
    unique: bool = False,
    line_ending: bytes = b"\n",
    comment_marker: str | None = None,
    ignore_leading_whitespace: bool = False,
    ignore_trailing_whitespace: bool = False,
    create_if_missing: bool = True,
    make_parents: bool = False,
    unlink_first: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Append a single line to a file with automatic line ending.

    Args:
        line: The line to append (without newline)
        path: Path to the file
        unique: Only append if line not already present
        line_ending: Line ending to use (default: LF)
        comment_marker: Optional comment marker for unique comparison
        ignore_leading_whitespace: Ignore leading whitespace in unique comparison
        ignore_trailing_whitespace: Ignore trailing whitespace in unique comparison
        create_if_missing: Create file if it doesn't exist
        make_parents: Create parent directories if needed
        unlink_first: Unlink file before writing (requires unique=True)
        dry_run: Show what would be written without modifying file

    Returns:
        Number of bytes written (0 if already present with unique=True)

    Raises:
        ValueError: If line is empty or contains line_ending
        ValueError: If unlink_first=True without unique=True
        ValueError: If make_parents=True without create_if_missing=True
        ValueError: If whitespace flags used without unique=True
    """
    # Validation
    if len(line) == 0:
        raise ValidationError(
            "Line must not be empty", cli_msg="LINE must not be empty"
        )

    if unlink_first and not unique:
        raise ValidationError(
            "unlink_first=True requires unique=True",
            cli_msg="--unlink-first requires --unique",
        )

    if make_parents and not create_if_missing:
        raise ValidationError(
            "make_parents=True requires create_if_missing=True",
            cli_msg="--make-parents requires file creation (do not use --do-not-create)",
        )

    if ignore_leading_whitespace and not unique:
        raise ValidationError(
            "ignore_leading_whitespace=True requires unique=True",
            cli_msg="--ignore-leading-whitespace requires --unique",
        )

    if ignore_trailing_whitespace and not unique:
        raise ValidationError(
            "ignore_trailing_whitespace=True requires unique=True",
            cli_msg="--ignore-trailing-whitespace requires --unique",
        )

    # Encode line
    line_bytes = line.encode("utf-8", errors="strict")

    # Check for embedded line endings
    if line_ending in line_bytes:
        raise ValidationError(
            f"Line contains the line_ending delimiter ({line_ending!r}). "
            f"Options: (1) Use separate calls for multiple lines, "
            f"(2) Use append_bytes for multi-line data, or "
            f"(3) Choose a different line_ending that doesn't appear in your data.",
            cli_msg=(
                f"Line contains the line_ending delimiter ({line_ending!r}). "
                f"Options: (1) Use separate calls for multiple lines, "
                f"(2) Use 'append-bytes' for multi-line data, or "
                f"(3) Choose a different --line-ending that doesn't appear in your data."
            ),
        )

    # Add line ending
    bytes_payload = line_bytes + line_ending

    # Dry run
    if dry_run:
        return len(bytes_payload)

    # Write
    return append_bytes_to_file(
        bytes_payload=bytes_payload,
        path=path,
        unique_bytes=unique,
        create_if_missing=create_if_missing,
        make_parents=make_parents,
        unlink_first=unlink_first,
        line_ending=line_ending if unique else None,
        comment_marker=comment_marker.encode("utf8") if comment_marker else None,
        ignore_leading_whitespace=ignore_leading_whitespace,
        ignore_trailing_whitespace=ignore_trailing_whitespace,
    )


def append_bytes(
    *,
    data: bytes,
    path: Path,
    unique: bool = False,
    create_if_missing: bool = True,
    make_parents: bool = False,
    unlink_first: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Append raw bytes to a file without modification.

    Args:
        data: The bytes to append
        path: Path to the file
        unique: Only append if bytes not already present (uses substring search)
        create_if_missing: Create file if it doesn't exist
        make_parents: Create parent directories if needed
        unlink_first: Unlink file before writing (requires unique=True)
        dry_run: Show what would be written without modifying file

    Returns:
        Number of bytes written (0 if already present with unique=True)

    Raises:
        ValueError: If data is empty
        ValueError: If unlink_first=True without unique=True
        ValueError: If make_parents=True without create_if_missing=True
    """
    # Validation
    if len(data) == 0:
        raise ValidationError(
            "Data must not be empty", cli_msg="BYTES must not be empty"
        )

    if unlink_first and not unique:
        raise ValidationError(
            "unlink_first=True requires unique=True",
            cli_msg="--unlink-first requires --unique",
        )

    if make_parents and not create_if_missing:
        raise ValidationError(
            "make_parents=True requires create_if_missing=True",
            cli_msg="--make-parents requires file creation (do not use --do-not-create)",
        )

    # Dry run
    if dry_run:
        return len(data)

    # Write
    return append_bytes_to_file(
        bytes_payload=data,
        path=path,
        unique_bytes=unique,
        create_if_missing=create_if_missing,
        make_parents=make_parents,
        unlink_first=unlink_first,
        line_ending=None,  # Binary mode - no line ending
        comment_marker=None,
        ignore_leading_whitespace=False,
        ignore_trailing_whitespace=False,
    )


# =============================================================================
# Click CLI setup
# =============================================================================


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

    # CLI-only validation
    if not len(lines) > 0:
        raise click.ClickException("At least one LINE must be specified.")

    # Map line ending code to bytes
    line_ending_dict = {
        "LF": b"\n",
        "CRLF": b"\r\n",
        "CR": b"\r",
    }
    line_ending = line_ending_dict[line_ending_code]
    create_if_missing = not do_not_create_if_missing

    # Process each line
    for line in lines:
        if dry_run:
            click.echo(
                f"[filetool append-line][dry-run] Would write: "
                f"{(line.encode('utf-8') + line_ending)!r} to {path}"
            )
            continue

        try:
            bytes_written = append_line(
                line=line,
                path=path,
                unique=unique_line,
                line_ending=line_ending,
                comment_marker=comment_marker,
                ignore_leading_whitespace=ignore_leading_whitespace,
                ignore_trailing_whitespace=ignore_trailing_whitespace,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first,
                dry_run=False,  # Already handled above
            )

            if bytes_written:
                click.echo(
                    f"[filetool append-line] Wrote {bytes_written} bytes to {path}"
                )
        except ValidationError as e:
            # Use CLI-friendly message if available
            raise click.ClickException(e.cli_msg or str(e)) from e


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
    help="Insert bytes from a file instead of positional args.",
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

    # CLI-only validation
    if not (len(byte_vectors) > 0 or bytes_from_path):
        raise click.ClickException(
            "At least one of BYTES or --bytes-from-path must be specified."
        )
    if len(byte_vectors) > 0 and bytes_from_path:
        raise click.ClickException(
            "BYTES and --bytes-from-path are mutually exclusive."
        )

    create_if_missing = not do_not_create_if_missing

    # Collect all byte payloads
    bytes_payloads = []
    if bytes_from_path:
        try:
            with open(bytes_from_path, "rb") as fh:
                bytes_payloads.append(fh.read())
        except OSError as e:
            raise click.ClickException(f"Failed to read {bytes_from_path}: {e}") from e
    else:
        for bv in byte_vectors:
            if len(bv) == 0:
                raise click.ClickException("Cannot write empty input")
            try:
                if hex_input:
                    data = bytes.fromhex(bv)
                else:
                    data = bv.encode("utf-8", errors="strict")
                bytes_payloads.append(data)
            except ValueError as e:
                raise click.ClickException(f"Invalid input: {e}") from e

    # Write each payload
    for data in bytes_payloads:
        if dry_run:
            click.echo(
                f"[filetool append-bytes][dry-run] Would write: {data!r} to {path}"
            )
            continue

        try:
            bytes_written = append_bytes(
                data=data,
                path=path,
                unique=unique_bytes,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first,
                dry_run=False,  # Already handled above
            )

            if bytes_written:
                click.echo(f"[filetool] Wrote {bytes_written} bytes to {path}")
        except ValidationError as e:
            # Use CLI-friendly message if available
            raise click.ClickException(e.cli_msg or str(e)) from e


if __name__ == "__main__":
    cli.main(args=sys.argv[1:], standalone_mode=True)
