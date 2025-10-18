#!/usr/bin/env python3
# tab-width:4

"""
Public API function for appending lines to files with CLI support.
"""

from __future__ import annotations

from pathlib import Path

from .filetool import append_bytes_to_file
from .validation import ValidationError


def append_line_to_path(
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
            f"(2) Use append_bytes_to_path for multi-line data, or "
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
