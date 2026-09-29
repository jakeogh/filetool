#!/usr/bin/env python3
# tab-width:4

from __future__ import annotations

import fcntl
import os
import stat
import tempfile
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from typing import BinaryIO

from .splitlines_bytes import splitlines_bytes
from .validate_args import _validate_args

__all__ = [
    "ensure_line_in_config_file",
    "comment_out_line_in_file",
    "uncomment_line_in_file",
]

Constraint = dict[str, Any]


@contextmanager
def _directory_lock(directory: Path) -> Iterator[int]:
    # flock on the directory serializes every filetool operation inside it,
    # including rename-based replacement, without a lockfile that outlives the call
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _locked_file_handle(
    *,
    path: Path,
    create: bool,
) -> Iterator[BinaryIO]:
    flags = os.O_RDWR | (os.O_CREAT if create else 0)
    fd = os.open(path, flags, 0o666)
    with os.fdopen(fd, "rb+") as fh:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fh


def find_bytes_offset_in_stream(
    stream: BinaryIO,
    *,
    target: bytes,
    chunk_size: int = 1024 * 1024,
) -> int | None:
    if not target:
        raise ValueError("Target bytes must not be empty")

    overlap = len(target) - 1
    offset = 0
    previous = b""

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return None

        haystack = previous + chunk
        pos = haystack.find(target)
        if pos != -1:
            return offset - len(previous) + pos

        offset += len(chunk)
        previous = haystack[-overlap:] if overlap > 0 else b""


def _write_and_sync(fh: BinaryIO, data: bytes) -> None:
    fh.write(data)
    fh.flush()
    os.fsync(fh.fileno())


_APPEND_CONSTRAINTS: dict[str, Constraint] = {
    "bytes_payload": {"type": bytes, "not_empty": True},
    "path": {"type": Path},
    "unlink_first": {"type": bool, "requires_if": [("create_if_missing", True)]},
    "unique_bytes": {"type": bool},
    "create_if_missing": {"type": bool},
    "make_parents": {"type": bool, "requires_if": [("create_if_missing", True)]},
    "line_ending": {"type": (bytes, type(None)), "nonempty_if_set": True},
    "comment_marker": {
        "type": (bytes, type(None)),
        "nonempty_if_set": True,
        "requires": ["unique_bytes"],
    },
    "ignore_leading_whitespace": {"type": bool, "requires": ["unique_bytes"]},
    "ignore_trailing_whitespace": {"type": bool, "requires": ["unique_bytes"]},
}


def _append_bytes_to_file(
    *,
    bytes_payload: bytes,
    path: Path,
    unlink_first: bool,
    unique_bytes: bool,
    create_if_missing: bool,
    make_parents: bool,
    line_ending: bytes | None = None,
    comment_marker: bytes | None = None,
    ignore_leading_whitespace: bool = False,
    ignore_trailing_whitespace: bool = False,
) -> int:
    """
    Append bytes_payload to path, returning the number of bytes written.

    Binary mode (line_ending=None): the payload is appended verbatim. With
    unique_bytes the payload is skipped if it occurs anywhere in the file.

    Line mode (line_ending set): the payload is one logical line ending in
    line_ending. If the file is non-empty and does not end with line_ending,
    the separator is written first and counted. With unique_bytes the payload
    is skipped if any existing line matches it after comment stripping and
    whitespace normalization; an unterminated final line counts as a line.

    unlink_first replaces the file with the payload under the same lock.
    Symlinks are resolved so the real file and its directory are locked.
    """
    _validate_args(
        function_name="_append_bytes_to_file",
        args=locals(),
        constraints=_APPEND_CONSTRAINTS,
    )
    if line_ending is None and (
        comment_marker is not None
        or ignore_leading_whitespace
        or ignore_trailing_whitespace
    ):
        raise ValueError(
            "comment_marker and whitespace options require line_ending (line mode)"
        )
    if (
        comment_marker is not None
        and line_ending is not None
        and line_ending in comment_marker
    ):
        raise ValueError("line_ending must not be contained in comment_marker")

    path = path.resolve()
    if make_parents:
        path.parent.mkdir(parents=True, exist_ok=True)

    with _directory_lock(path.parent):
        if unlink_first:
            path.unlink(missing_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            with os.fdopen(fd, "wb") as fh:
                _write_and_sync(fh, bytes_payload)
            return len(bytes_payload)

        with _locked_file_handle(path=path, create=create_if_missing) as fh:
            if unique_bytes:
                if line_ending is not None:
                    for line in splitlines_bytes(
                        fh,
                        delim=line_ending,
                        comment_marker=comment_marker,
                        strip_leading_whitespace=ignore_leading_whitespace,
                        strip_trailing_whitespace=ignore_trailing_whitespace,
                    ):
                        if not line.endswith(line_ending):
                            line += line_ending
                        if line == bytes_payload:
                            return 0
                elif (
                    find_bytes_offset_in_stream(
                        stream=fh, target=bytes_payload, chunk_size=8192
                    )
                    is not None
                ):
                    return 0

            size = os.fstat(fh.fileno()).st_size
            separator = b""
            if line_ending is not None and size >= len(line_ending):
                fh.seek(size - len(line_ending))
                if fh.read(len(line_ending)) != line_ending:
                    separator = line_ending
            fh.seek(0, os.SEEK_END)
            _write_and_sync(fh, separator + bytes_payload)
            return len(separator) + len(bytes_payload)


def _modify_file_lines(
    *,
    path: Path,
    line_transformer: Callable[[bytes], bytes],
    line_ending: bytes,
) -> int:
    """
    Rewrite path line by line through line_transformer, atomically.

    Each line is passed with its line_ending (the final line may lack one)
    and must be returned as bytes. Returns the number of lines the
    transformer changed. When nothing changes the file is not touched.

    The directory and the file are locked; the file's inode is checked
    between stat and open and again before the rename so a replacement by a
    non-cooperating writer aborts with OSError instead of being clobbered.
    Symlinks are resolved so the real file is replaced and the link survives.
    """
    if not isinstance(path, Path):
        raise TypeError(f"path must be Path, got {type(path).__name__}")
    if not isinstance(line_ending, bytes):
        raise TypeError(f"line_ending must be bytes, got {type(line_ending).__name__}")
    if len(line_ending) == 0:
        raise ValueError("line_ending must not be empty")
    if not callable(line_transformer):
        raise TypeError("line_transformer must be callable")

    path = path.resolve(strict=True)

    with _directory_lock(path.parent) as dir_fd:
        inode = path.stat().st_ino
        with _locked_file_handle(path=path, create=False) as fh:
            st = os.fstat(fh.fileno())
            if st.st_ino != inode:
                raise OSError(
                    f"File {path} was replaced between stat and open "
                    f"(inode changed from {inode} to {st.st_ino})"
                )
            lines = list(splitlines_bytes(fh, delim=line_ending))

        modified_count = 0
        new_lines: list[bytes] = []
        for line in lines:
            new_line = line_transformer(line)
            if not isinstance(new_line, bytes):
                raise TypeError(
                    f"line_transformer must return bytes, got {type(new_line).__name__}"
                )
            if new_line != line:
                modified_count += 1
            new_lines.append(new_line)

        if modified_count == 0:
            return 0

        tmp_fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_fh:
                tmp_fh.writelines(new_lines)
                tmp_fh.flush()
                os.fchmod(tmp_fd, stat.S_IMODE(st.st_mode))
                os.fchown(tmp_fd, st.st_uid, st.st_gid)
                os.fsync(tmp_fd)

            st_before_rename = path.stat()
            if st_before_rename.st_ino != inode:
                raise OSError(
                    f"File {path} was replaced before rename "
                    f"(inode changed from {inode} to {st_before_rename.st_ino})"
                )
            os.rename(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

        os.fsync(dir_fd)
        return modified_count


def _split_line_ending(line: bytes, line_ending: bytes) -> tuple[bytes, bytes]:
    if line.endswith(line_ending):
        return line[: -len(line_ending)], line_ending
    return line, b""


def _normalize_body(
    body: bytes,
    *,
    ignore_leading_whitespace: bool,
    ignore_trailing_whitespace: bool,
) -> bytes:
    if ignore_leading_whitespace:
        body = body.lstrip()
    if ignore_trailing_whitespace:
        body = body.rstrip()
    return body


def _validate_line_args(
    *,
    path: Path,
    line: str,
    comment_marker: str,
    line_ending: bytes,
) -> tuple[bytes, bytes]:
    if not isinstance(path, Path):
        raise TypeError(f"path must be Path, got {type(path).__name__}")
    if not isinstance(line, str):
        raise TypeError(f"line must be str, got {type(line).__name__}")
    if not isinstance(comment_marker, str):
        raise TypeError(
            f"comment_marker must be str, got {type(comment_marker).__name__}"
        )
    if not isinstance(line_ending, bytes):
        raise TypeError(f"line_ending must be bytes, got {type(line_ending).__name__}")
    if len(line) == 0:
        raise ValueError("line must not be empty")
    if len(comment_marker) == 0:
        raise ValueError("comment_marker must not be empty")
    if len(line_ending) == 0:
        raise ValueError("line_ending must not be empty")

    line_bytes = line.encode("utf-8", errors="strict")
    comment_prefix = (comment_marker + " ").encode("utf-8", errors="strict")
    if line_ending in line_bytes:
        raise ValueError(
            f"line contains the line_ending delimiter ({line_ending!r}). "
            f"This function operates on single lines only."
        )
    return line_bytes, comment_prefix


def comment_out_line_in_file(
    *,
    path: Path,
    line: str,
    comment_marker: str = "#",
    line_ending: bytes = b"\n",
    ignore_leading_whitespace: bool = True,
    ignore_trailing_whitespace: bool = True,
) -> int:
    """
    Prepend comment_marker and a space to every line matching line.

    Matching is done on the line body with the whitespace options applied;
    the original line is preserved after the inserted prefix. Lines that
    already carry the marker do not match. Returns the number of lines
    changed.
    """
    line_bytes, comment_prefix = _validate_line_args(
        path=path, line=line, comment_marker=comment_marker, line_ending=line_ending
    )

    def transformer(line_with_ending: bytes) -> bytes:
        body, _ = _split_line_ending(line_with_ending, line_ending)
        body = _normalize_body(
            body,
            ignore_leading_whitespace=ignore_leading_whitespace,
            ignore_trailing_whitespace=ignore_trailing_whitespace,
        )
        if body == line_bytes:
            return comment_prefix + line_with_ending
        return line_with_ending

    return _modify_file_lines(
        path=path,
        line_transformer=transformer,
        line_ending=line_ending,
    )


def uncomment_line_in_file(
    *,
    path: Path,
    line: str,
    comment_marker: str = "#",
    line_ending: bytes = b"\n",
    ignore_leading_whitespace: bool = True,
    ignore_trailing_whitespace: bool = True,
    multiple: bool = False,
) -> int:
    """
    Remove comment_marker and the following space from lines whose remaining
    body matches line. Indentation before the marker is preserved.

    With multiple=False only the first commented occurrence is uncommented.
    Returns the number of lines changed; 0 when the line is present but
    already uncommented. Raises ValueError if the line is found in neither
    form.
    """
    if not isinstance(multiple, bool):
        raise TypeError(f"multiple must be bool, got {type(multiple).__name__}")
    line_bytes, comment_prefix = _validate_line_args(
        path=path, line=line, comment_marker=comment_marker, line_ending=line_ending
    )

    found_uncommented = False
    found_commented = False
    uncommented_count = 0

    def normalize(body: bytes) -> bytes:
        return _normalize_body(
            body,
            ignore_leading_whitespace=ignore_leading_whitespace,
            ignore_trailing_whitespace=ignore_trailing_whitespace,
        )

    def transformer(line_with_ending: bytes) -> bytes:
        nonlocal found_uncommented, found_commented, uncommented_count
        body, _ = _split_line_ending(line_with_ending, line_ending)
        body = normalize(body)
        if body == line_bytes:
            found_uncommented = True
            return line_with_ending
        if not body.startswith(comment_prefix):
            return line_with_ending
        if normalize(body[len(comment_prefix) :]) != line_bytes:
            return line_with_ending
        found_commented = True
        if not multiple and uncommented_count > 0:
            return line_with_ending
        uncommented_count += 1
        indent = len(line_with_ending) - len(line_with_ending.lstrip())
        return (
            line_with_ending[:indent] + line_with_ending[indent + len(comment_prefix) :]
        )

    _modify_file_lines(
        path=path,
        line_transformer=transformer,
        line_ending=line_ending,
    )

    if not found_uncommented and not found_commented:
        raise ValueError(
            f"Line not found in file: {line!r}. "
            f"The line must exist (either commented or uncommented) to use this function."
        )
    return uncommented_count


def ensure_line_in_config_file(
    *,
    path: Path,
    line: str,
    comment_marker: str = "#",
    line_ending: bytes = b"\n",
    ignore_leading_whitespace: bool = True,
    ignore_trailing_whitespace: bool = True,
) -> int:
    """
    Append line (without line ending) to path unless an equivalent
    uncommented line is already present. Creates the file and parents.
    Returns the number of bytes written.
    """
    line_bytes = line.encode("utf8", errors="strict")
    if line_ending in line_bytes:
        raise ValueError(
            f"line contains the line_ending delimiter ({line_ending!r}). "
            f"Pass the line without line ending - it will be appended automatically."
        )
    return _append_bytes_to_file(
        bytes_payload=line_bytes + line_ending,
        path=path,
        unique_bytes=True,
        create_if_missing=True,
        make_parents=True,
        unlink_first=False,
        line_ending=line_ending,
        comment_marker=comment_marker.encode("utf8", errors="strict"),
        ignore_leading_whitespace=ignore_leading_whitespace,
        ignore_trailing_whitespace=ignore_trailing_whitespace,
    )
