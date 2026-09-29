#!/usr/bin/env python3
# tab-width:4

from __future__ import annotations

from pathlib import Path

from .filetool import _append_bytes_to_file
from .validation import ValidationError


def append_line_to_file(
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
) -> int:
    """
    Append line plus line_ending to path. A missing line_ending at the end
    of an existing file is written first. With unique, skip if an equivalent
    line is present. Returns the number of bytes written.
    """
    if len(line) == 0:
        raise ValidationError(
            "Line must not be empty", cli_msg="LINE must not be empty"
        )

    if unlink_first and not create_if_missing:
        raise ValidationError(
            "unlink_first=True requires create_if_missing=True",
            cli_msg="--unlink-first requires file creation (do not use --do-not-create)",
        )

    if make_parents and not create_if_missing:
        raise ValidationError(
            "make_parents=True requires create_if_missing=True",
            cli_msg="--make-parents requires file creation (do not use --do-not-create)",
        )

    if comment_marker is not None and not unique:
        raise ValidationError(
            "comment_marker requires unique=True",
            cli_msg="--comment-marker requires --unique",
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

    line_bytes = line.encode("utf-8", errors="strict")

    if line_ending in line_bytes:
        raise ValidationError(
            f"Line contains the line_ending delimiter ({line_ending!r}). "
            f"Options: (1) Use separate calls for multiple lines, "
            f"(2) Use append_bytes_to_file for multi-line data, or "
            f"(3) Choose a different line_ending that doesn't appear in your data.",
            cli_msg=(
                f"Line contains the line_ending delimiter ({line_ending!r}). "
                f"Options: (1) Use separate calls for multiple lines, "
                f"(2) Use 'append-bytes' for multi-line data, or "
                f"(3) Choose a different --line-ending that doesn't appear in your data."
            ),
        )

    return _append_bytes_to_file(
        bytes_payload=line_bytes + line_ending,
        path=path,
        unique_bytes=unique,
        create_if_missing=create_if_missing,
        make_parents=make_parents,
        unlink_first=unlink_first,
        line_ending=line_ending,
        comment_marker=comment_marker.encode("utf8")
        if comment_marker is not None
        else None,
        ignore_leading_whitespace=ignore_leading_whitespace,
        ignore_trailing_whitespace=ignore_trailing_whitespace,
    )
