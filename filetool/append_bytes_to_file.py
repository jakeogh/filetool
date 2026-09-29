#!/usr/bin/env python3
# tab-width:4

from __future__ import annotations

from pathlib import Path

from .filetool import _append_bytes_to_file
from .validation import ValidationError


def append_bytes_to_file(
    *,
    data: bytes,
    path: Path,
    unique: bool = False,
    create_if_missing: bool = True,
    make_parents: bool = False,
    unlink_first: bool = False,
) -> int:
    """
    Append raw bytes to path. With unique, skip if data occurs anywhere in
    the file. Returns the number of bytes written.
    """
    if len(data) == 0:
        raise ValidationError(
            "Data must not be empty", cli_msg="BYTES must not be empty"
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

    return _append_bytes_to_file(
        bytes_payload=data,
        path=path,
        unique_bytes=unique,
        create_if_missing=create_if_missing,
        make_parents=make_parents,
        unlink_first=unlink_first,
    )
