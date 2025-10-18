#!/usr/bin/env python3
# tab-width:4

"""
Public API function for appending bytes to files with CLI support.
"""

from __future__ import annotations

from pathlib import Path

from .filetool import append_bytes_to_file
from .validation import ValidationError


def append_bytes_to_path(
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
