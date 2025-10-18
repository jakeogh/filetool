#!/usr/bin/env python3
# -*- coding: utf8 -*-
# tab-width:4

# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive(!)

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from typing import BinaryIO
from typing import cast

# from rich.traceback import install
# install(show_locals=True)

__all__ = [
    "append_bytes_to_file",
    "locked_file_handle",
    "splitlines_bytes",
    "ensure_bytes_present",
    "ensure_line_in_config_file",
    "open_eintr_safe",
]

Constraint = dict[str, Any]

DEFAULT_LOCK_DIR = Path("/tmp/filetool-locks")
LOCK_DIR = Path(os.environ.get("FILETOOL_LOCK_DIR", DEFAULT_LOCK_DIR))
LOCK_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def get_lockfile_path(target_path: Path) -> Path:
    canonical_path = str(target_path.resolve())
    digest = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()
    return LOCK_DIR / digest


def fsync_eintr_safe(fd: int):
    while True:
        try:
            return os.fsync(fd)
        except OSError as e:
            if e.errno == errno.EINTR:
                continue
            raise


def open_eintr_safe(*args, **kwargs):
    while True:
        try:
            return os.open(*args, **kwargs)
        except OSError as e:
            if e.errno == errno.EINTR:
                continue
            raise


def open_with_mode(
    path: os.PathLike,
    flags: int,
    mode: int,
) -> int:
    old_umask = os.umask(0)
    try:
        return open_eintr_safe(path, flags, mode)
    finally:
        os.umask(old_umask)


@contextmanager
def locked_file_handle(
    *,
    path: Path,
    mode: str,
    blocking: bool,
    create: bool,
) -> Iterator[BinaryIO]:
    """
    Open a file with an advisory exclusive lock.

    This context manager wraps `open()` and applies a `fcntl.flock()` exclusive lock
    to the opened file handle. It ensures that only one cooperating process can access
    the file at a time.

    Advisory locks are:
        - Enforced by the OS *only if all processes honor them*
        - Effective on local filesystems and NFSv4
        - Not enforced on NFSv3 unless `lockd` is properly configured and not mounted with `nolock`

    Parameters:
        path (Path): Path to the file to open and lock.
        mode (str): File open mode (e.g., 'rb', 'rb+', 'wb'). Must be provided explicitly.
        create (bool): If True, atomically create the file before opening (if it does not exist).
        blocking (bool):
            - If True (default): wait until the lock can be acquired.
            - If False: acquire the lock non-blocking. Raises BlockingIOError if lock is held.

    Yields:
        BinaryIO: A file object with an exclusive lock held.

    Raises:
        BlockingIOError: If blocking is False and the lock cannot be acquired.
        OSError: If the lock cannot be established (e.g., NFSv3 without lockd).

    Notes:
        - This function is safe under NFSv4.
        - Under NFSv3, locking may silently fail or raise ENOLCK if unsupported.
        - Use only when all accessors of the file cooperate with this locking mechanism.
        - This does not protect against non-cooperating writers or low-level race conditions.

    Example:
        >>> with locked_file_handle(Path("/tmp/data.bin"), mode="rb+") as fh:
        >>>     data = fh.read()
        >>>     fh.seek(0)
        >>>     fh.write(data + b"\n")

    Note:
        - This only applies file-level advisory locking via `fcntl.flock`.
        - To ensure inter-process correctness, this is typically used *alongside a global per-path lockfile* (see `ensure_bytes_present()`).
        - Guarantees release of lock even if close() fails.
        - Escalates via os.close(fileno()) if necessary.
        - Emits warnings instead of silently failing on unlock/close.
    """
    if create:
        # flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        # Must use O_RDWR here for some platforms: later re-open expects 'rb+' (read/write)
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        try:
            fd = open_eintr_safe(path, flags)
            os.close(fd)
        except FileExistsError:
            pass

    is_binary = "b" in mode  # todo validate all modes
    assert is_binary
    fh = cast(BinaryIO, open(path, mode, encoding=None))
    # fh = open(path, mode, encoding=None) if "b" in mode else open(path, mode, encoding="utf-8")
    lock_mode = fcntl.LOCK_EX
    if not blocking:
        lock_mode |= fcntl.LOCK_NB

    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), lock_mode)
                break  # success
            except InterruptedError:
                continue  # Retry on EINTR
            except BlockingIOError:
                fh.close()
                raise
            except OSError as e:
                if e.errno == errno.EINTR:
                    continue
                fh.close()
                if e.errno == errno.ENOLCK:
                    raise OSError(
                        "Locking unavailable (ENOLCK). Possibly NFSv3 or misconfigured lockd."
                    ) from e
                raise

        yield fh

    finally:
        try:
            if not fh.closed:
                fileno = fh.fileno()
                try:
                    fcntl.flock(fileno, fcntl.LOCK_UN)
                except OSError as e:
                    print(
                        f"Warning: failed to unlock file {path}: {e}", file=sys.stderr
                    )
            fh.close()
        except Exception as e:
            print(
                f"Warning: error during final cleanup of file {path}: {e}",
                file=sys.stderr,
            )


def splitlines_bytes(
    data: bytes | BinaryIO,
    *,
    delim: bytes = b"\n",
    comment_marker: None | bytes = None,
    strip_leading_whitespace: bool = False,
    strip_trailing_whitespace: bool = False,
    chunk_size: int = 8192,
) -> Iterator[bytes]:
    """
    Split raw bytes by a delimiter, optionally stripping whitespace or comments.

    Parameters:
        data (bytes | BinaryIO): Raw byte buffer or readable binary file-like object.
        delim (bytes): Delimiter to split on (default: b'\\n').
        comment_marker (bytes | None): If set, strip trailing content starting at this marker.
        strip_leading_whitespace (bool): Whether to strip leading whitespace from each line.
        strip_trailing_whitespace (bool): Whether to strip trailing whitespace from each line.
        chunk_size (int): Number of bytes to read from a BinaryIO object at a time.

    Yields:
        bytes: Processed line segments, possibly with delimiters retained (depending on settings).

    Note:
        - Unlike `bytes.splitlines()`, this supports custom delimiters, comment stripping, and whitespace control.
        - If `data` is a file-like object (e.g. `BinaryIO`), it will be read in chunks with minimal memory usage.
        - A trailing empty segment is not emitted unless explicitly present as part of a delimiter.
    """
    # comment_marker can be in delim:
    # list(splitlines_bytes(data=b'payload###comment##next', delim=b'##', comment_marker=b'#'))
    # -> [b'payload##', b'##', b'next']

    # but delim in comment marker is disallowed because it silently disables comment stripping:
    # list(splitlines_bytes(data=b'payload###comment##next', delim=b'#', comment_marker=b'##'))
    # [b'payload#', b'#', b'#', b'comment#', b'#', b'next']

    if delim is None or len(delim) == 0:
        raise ValueError("delim must not be empty")

    if comment_marker is not None:
        if len(comment_marker) == 0:
            raise ValueError("comment_marker must not be empty")
        if not isinstance(comment_marker, bytes):
            raise TypeError("comment_marker must be bytes or None")
        if comment_marker == delim:
            # if this was allowed, it would silently disable comment stripping
            raise ValueError("comment_marker can not match delim")
        if comment_marker is not None and delim in comment_marker:
            # if this was allowed, it would silently disable comment stripping
            raise ValueError("delim must not be contained in comment_marker")

    strip_bytes = b" \t\n\r\x0b\x0c"  # changing this would be a bug becuase it's what l/rstrip use
    re_add_delim = delim in strip_bytes
    delim_len = len(delim)
    buffer = b""

    def process_line(line: bytes) -> None | bytes:
        _line = line
        if comment_marker and comment_marker in line:
            _line = line.split(comment_marker)[0]
            if line.endswith(delim):
                _line = _line + delim

        if strip_leading_whitespace:
            if line.endswith(delim):
                _line = _line.lstrip()
                if len(_line) == 0:
                    _line += delim
            else:
                _line = _line.lstrip()
        if strip_trailing_whitespace:
            if re_add_delim:
                _line = _line.rstrip() + delim
            else:
                _line = _line.rstrip()
            if _line == b"":
                return None
        if strip_leading_whitespace:
            if _line == b"":
                return None
        if comment_marker and comment_marker in line:
            if _line == b"":
                return None
        # assert len(_line) > 0
        return _line

    if isinstance(data, bytes):
        start = 0
        while True:
            idx = data.find(delim, start)
            if idx == -1:
                if start < len(data):
                    line = data[start:]
                    _pl = process_line(line)
                    if _pl is not None:
                        yield _pl
                break
            end = idx + delim_len
            line = data[start:end]
            _pl = process_line(line)
            if _pl is not None:
                yield _pl
            start = end
    else:
        while True:
            chunk = data.read(chunk_size)
            if not chunk:
                break
            buffer += chunk
            while True:
                idx = buffer.find(delim)
                if idx == -1:
                    break
                end = idx + delim_len
                line = buffer[:end]
                _pl = process_line(line)
                if _pl is not None:
                    yield _pl
                buffer = buffer[end:]

        if buffer:
            _pl = process_line(buffer)
            if _pl is not None:
                yield _pl


@contextmanager
def safe_open_rw_binary(
    path: Path,
    *,
    require_exists: bool,
) -> Iterator[BinaryIO]:
    """
    Open a file in 'rb+' mode, atomically creating it if it doesn't exist,
    and acquire an advisory exclusive lock.

    This wraps `locked_file_handle()` and ensures the file exists beforehand,
    avoiding race conditions with concurrent creators.

    - If the file exists: opens in 'rb+' without altering timestamps.
    - If the file doesn't exist: creates it atomically with 'xb' mode.
    - If another process wins the race to create the file: reopens it safely.

    Yields:
        BinaryIO: A file object locked and opened in 'rb+' mode.
    """
    try:
        with locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=False,
        ) as fh:
            yield fh
    except FileNotFoundError:
        if require_exists:
            raise
        with locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=True,
        ) as fh:
            yield fh


def validate_args(
    *,
    function_name: str,
    args: dict,
    constraints: dict[str, Constraint],
    conflicts: list[tuple] | None = None,
) -> None:
    conflicts = conflicts or []

    for param, rules in constraints.items():
        val = args.get(param)

        # Type check
        if "type" in rules and not isinstance(val, rules["type"]):
            raise TypeError(
                f"{function_name}() {param} must be of type {rules['type']}, got {type(val).__name__}"
            )

        # Not empty check
        if rules.get("not_empty") and val == b"":
            raise ValueError(f"{function_name}() {param} must not be empty")

        # Must not be empty if set
        if rules.get("nonempty_if_set") and val is not None and len(val) == 0:
            raise ValueError(f"{function_name}() {param} must not be empty if set")

        # Requires other parameters
        if "requires" in rules:
            for required_param in rules["requires"]:
                required_val = args.get(required_param)
                if isinstance(val, bool):
                    if val and required_val is not True:
                        raise ValueError(
                            f"{function_name}() {param}=True requires {required_param}=True"
                        )
                elif val is not None and required_val is not True:
                    raise ValueError(
                        f"{function_name}() {param} requires {required_param}=True"
                    )

            for dep_param, expected_value in rules.get("requires_if", []):
                if args.get(dep_param) != expected_value:
                    raise ValueError(
                        f"{function_name}() {param}=True requires {dep_param}={expected_value}"
                    )

        # Requires nonempty parameters if this is True
        if "requires_nonempty" in rules:
            for required_param in rules["requires_nonempty"]:
                required_val = args.get(required_param)
                if val is True and (required_val is None or len(required_val) == 0):
                    raise ValueError(
                        f"{function_name}() {param}=True requires {required_param} to be non-empty"
                    )

    # Conflicts (apply unconditionally)
    for a, a_val, b, b_val, msg in conflicts:
        if args.get(a) == a_val and args.get(b) == b_val:
            raise ValueError(f"{function_name}()" + msg)


def find_bytes_offset_in_stream(
    stream: BinaryIO,
    *,
    target: bytes,
    chunk_size: int = 1024 * 1024,
) -> int | None:
    """
    Search for the first occurrence of a byte sequence in a binary stream and return its offset.

    Args:
        stream (BinaryIO): An open file-like object in binary mode, seeked to the desired start position.
        target (bytes): The exact byte sequence to locate. Must be non-empty.
        chunk_size (int): Number of bytes to read at a time. Default is 1 MiB.

    Returns:
        int | None: The byte offset of the first match from the current stream position, or None if not found.

    Raises:
        ValueError: If `target` is empty.
    """
    if not target:
        raise ValueError("Target bytes must not be empty")

    overlap = len(target) - 1
    offset = 0
    previous = b""

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break

        haystack = previous + chunk
        pos = haystack.find(target)
        if pos != -1:
            return offset - len(previous) + pos

        offset += len(chunk)
        previous = haystack[-overlap:] if overlap > 0 else b""

    return None


def ensure_bytes_present(
    *,
    path: Path,
    bytes_payload: bytes,
    unique_bytes: bool,
    create_if_missing: bool,
    make_parents: bool,
    line_ending: None | bytes,
    comment_marker: None | bytes,
    ignore_leading_whitespace: bool,
    ignore_trailing_whitespace: bool,
) -> int:
    """
    Ensure that `bytes_payload` is present in the file at `path`.

    If `unique_bytes` is False:
        - Appends `bytes_payload` directly (after acquiring global + file lock).

    If `unique_bytes` is True:
        - Reads the entire file into memory.
        - If `line_ending` is provided:
            - Parses the file into logical lines using `splitlines_bytes()`.
            - Compares each line to `bytes_payload`, respecting comment markers and whitespace options.
            - Only appends `bytes_payload` if no matching line is found.
        - If `line_ending` is None:
            - Performs binary substring search using `find_bytes_offset_in_stream()`.
            - Only appends `bytes_payload` if the exact byte sequence is not found anywhere in the file.
            - Note: `comment_marker`, `ignore_leading_whitespace`, and `ignore_trailing_whitespace`
              have no effect when `line_ending=None` (binary mode).

    This function:
        - Uses a SHA256-based global lockfile in `/tmp/filetool-locks` to ensure only one process modifies `path` at a time.
        - Also uses advisory `fcntl.flock()` on the target file itself.
        - Optionally creates the file and parent directories.

    Performance:
        - Fast for small/medium files.
        - Reads the entire file into memory when `unique_bytes` is True.

    Raises:
        - TypeError, ValueError, OSError for parameter validation and I/O errors.
    """

    PARAM_CONSTRAINTS: dict[str, Constraint] = {
        "path": {
            "type": Path,
        },
        "bytes_payload": {
            "type": bytes,
            "not_empty": True,
        },
        "unique_bytes": {
            "type": bool,
        },
        "create_if_missing": {
            "type": bool,
        },
        "make_parents": {
            "type": bool,
            "requires_if": [("create_if_missing", True)],
        },
        "line_ending": {
            "type": (bytes, type(None)),
            "nonempty_if_set": True,
            "requires": ["unique_bytes"],
        },
        "comment_marker": {
            "type": (bytes, type(None)),
            "nonempty_if_set": True,
            "requires": ["unique_bytes"],
        },
        "ignore_leading_whitespace": {
            "type": bool,
            "requires": ["unique_bytes"],
        },
        "ignore_trailing_whitespace": {
            "type": bool,
            "requires": ["unique_bytes"],
        },
    }

    CONFLICTS: list[tuple] = [
        (
            "make_parents",
            True,
            "create_if_missing",
            False,
            "make_parents=True requires create_if_missing=True",
        ),
    ]

    validate_args(
        function_name="ensure_bytes_present",
        args=locals(),
        constraints=PARAM_CONSTRAINTS,
        conflicts=CONFLICTS,
    )

    # must be checked manually
    if comment_marker is not None and comment_marker == line_ending:
        raise ValueError("comment_marker can not match delim")

    if make_parents:
        path.parent.mkdir(parents=True, exist_ok=True)

    # global lock to allow mutiple instances to run concurrently without file corruption
    lock_path = get_lockfile_path(path)
    # without 0o666 the root user might create a lockfile that the normal user cant acquire a lock on.
    lock_fd = open_with_mode(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o666)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        with locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=create_if_missing,
        ) as fh:
            fh.seek(0)
            if unique_bytes:
                if line_ending is not None:
                    for line in splitlines_bytes(
                        fh,
                        delim=line_ending,
                        comment_marker=comment_marker,
                        strip_leading_whitespace=ignore_leading_whitespace,
                        strip_trailing_whitespace=ignore_trailing_whitespace,
                    ):
                        if line == bytes_payload:
                            return 0
                else:
                    _offset = find_bytes_offset_in_stream(
                        stream=fh,
                        target=bytes_payload,
                        chunk_size=8192,
                    )
                    if _offset is not None:
                        return 0

            fh.seek(0, os.SEEK_END)
            fh.write(bytes_payload)
            fh.flush()
            fsync_eintr_safe(fh.fileno())
            return len(bytes_payload)
    finally:
        os.close(lock_fd)


def append_bytes_to_file(
    *,
    bytes_payload: bytes,
    path: Path,
    unlink_first: bool,
    unique_bytes: bool,
    create_if_missing: bool,
    make_parents: bool,
    line_ending: None | bytes = None,
    comment_marker: None | bytes = None,
    ignore_leading_whitespace: bool = False,
    ignore_trailing_whitespace: bool = False,
) -> int:
    """
    Append or ensure presence of a byte sequence in a file.

    This function either appends `bytes_payload` to `path` unconditionally,
    or checks for its presence using logical line comparison (if `unique_bytes=True`)
    before appending. It supports advisory locking, atomic creation, and optional
    directory creation. Input must be raw bytes; no encoding or decoding is performed.

    Parameters:
        bytes_payload (bytes): The byte sequence to append. Must not be empty.
        path (Path): The target file to append to.
        unlink_first (bool): If True, unlink the file before writing. Requires `unique_bytes=True`.
        unique_bytes (bool): If True, do not append if the payload is already present.
        create_if_missing (bool): If True, create the file if it doesn't exist.
        make_parents (bool): If True, create parent directories if needed. Requires `create_if_missing=True`.
        line_ending (bytes | None): Logical line ending used for deduplication. Required if `unique_bytes=True`.
        comment_marker (bytes | None): Optional comment prefix to strip during deduplication. Requires `unique_bytes=True`.
        ignore_leading_whitespace (bool): Ignore leading whitespace when checking for uniqueness.
        ignore_trailing_whitespace (bool): Ignore trailing whitespace when checking for uniqueness.

    Returns:
        int: The number of bytes written (equal to `len(bytes_payload)` if written, else 0).

    Raises:
        TypeError: On invalid parameter types.
        ValueError: On conflicting options or invalid settings.
        FileExistsError: If unlinking fails due to a race.
        FileNotFoundError: If writing is disallowed due to missing file/parents.
        OSError: For lower-level I/O issues.
    """

    # Constraint table for each parameter
    PARAM_CONSTRAINTS: dict[str, Constraint] = {
        "bytes_payload": {
            "type": bytes,
            "not_empty": True,
        },
        "path": {
            "type": Path,
        },
        "unlink_first": {
            "type": bool,
            "requires": ["unique_bytes"],
        },
        "unique_bytes": {
            "type": bool,
        },
        "create_if_missing": {
            "type": bool,
        },
        "make_parents": {
            "type": bool,
            "requires_if": [("create_if_missing", True)],
        },
        "line_ending": {
            "type": (bytes, type(None)),
            "nonempty_if_set": True,
            "requires": ["unique_bytes"],
        },
        "comment_marker": {
            "type": (bytes, type(None)),
            "requires": ["unique_bytes"],
            "nonempty_if_set": True,
        },
        "ignore_leading_whitespace": {
            "type": bool,
            "requires": ["unique_bytes"],
        },
        "ignore_trailing_whitespace": {
            "type": bool,
            "requires": ["unique_bytes"],
        },
    }

    # Custom conflict rules
    #  This cannot be encoded using requires, because the condition is:
    #  make_parents=True is not valid unless create_if_missing=True
    #  but create_if_missing does not depend on make_parents.
    CONFLICTS = [
        (
            "make_parents",
            True,
            "create_if_missing",
            False,
            "make_parents=True requires create_if_missing=True",
        ),
    ]

    validate_args(
        function_name="append_bytes_to_file",
        args=locals(),
        constraints=PARAM_CONSTRAINTS,
        conflicts=CONFLICTS,
    )

    if unlink_first:
        assert unique_bytes
        try:
            path.unlink()
        except FileNotFoundError:
            pass  # handle race below

        if make_parents:
            path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "xb") as fh:
                fh.write(bytes_payload)
                fh.flush()
                fsync_eintr_safe(fh.fileno())
        except FileExistsError as exc:
            raise FileExistsError(
                f"Race detected: file {path} was recreated before atomic write (unlink_first=True)"
            ) from exc
        return len(bytes_payload)

    # Attempt to open the file for read/write. This block only handles the case
    # where the file already exists.
    #
    # If this succeeds:
    # - If unique_bytes is False, write the bytes_payload immediately.
    # - If unique_bytes is True, write the bytes_payload only if it's not already present.
    #
    # Fall back to create file (and parent dir if allowed)
    try:
        bytes_written = ensure_bytes_present(
            path=path,
            bytes_payload=bytes_payload,
            unique_bytes=unique_bytes,
            create_if_missing=False,
            make_parents=False,
            line_ending=line_ending,
            comment_marker=comment_marker,
            ignore_leading_whitespace=ignore_leading_whitespace,
            ignore_trailing_whitespace=ignore_trailing_whitespace,
        )
        return bytes_written

    # File (or its parent) does not exist.
    # We may attempt creation, depending on create_if_missing and make_parents flags.
    # unique_line could be True or False.
    except FileNotFoundError:
        if not create_if_missing:
            # Caller forbids file creation; surface the error.
            raise

        # create_if_missing == True
        # make_parents could be True or False
        # we only want to attempt to make the parents if we try and fail to create the file
        # there is a race condition, some other process could create the file here
        # which would be ok, because create_if_missing == True
        # unique_line could be True or False

        try:
            # Use safe_open_rw_binary to handle 'rb+' access race-safely:
            # - File may not exist yet (create it)
            # - Or it may exist already due to a race (open it safely)
            # - Either way, we may need to read it if a race created it already

            bytes_written = ensure_bytes_present(
                path=path,
                bytes_payload=bytes_payload,
                unique_bytes=unique_bytes,
                create_if_missing=True,
                make_parents=make_parents,
                line_ending=line_ending,
                comment_marker=comment_marker,
                ignore_leading_whitespace=ignore_leading_whitespace,
                ignore_trailing_whitespace=ignore_trailing_whitespace,
            )
            return bytes_written

        # Likely cause: missing parent directory.
        # If allowed, attempt creation and retry the write.
        except FileNotFoundError:
            if make_parents:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Parent was created or race-lost. Proceed with write attempt.

            # We don't catch FileNotFoundError here:
            # - If it happens again, the parent was likely removed by another race.
            # - At this point, we've already tried to ensure the directory exists.
            # - Let the error surface for visibility instead of silently looping.
            bytes_written = ensure_bytes_present(
                path=path,
                bytes_payload=bytes_payload,
                unique_bytes=unique_bytes,
                create_if_missing=True,
                make_parents=make_parents,
                line_ending=line_ending,
                comment_marker=comment_marker,
                ignore_leading_whitespace=ignore_leading_whitespace,
                ignore_trailing_whitespace=ignore_trailing_whitespace,
            )
            return bytes_written


def ensure_line_in_config_file(
    *,
    path: Path,
    line: str,
    comment_marker: str,
    ignore_leading_whitespace: bool,
):

    _bytes = line.encode("utf8", errors="strict")
    _ = append_bytes_to_file(
        bytes_payload=_bytes,
        path=path,
        unique_bytes=True,
        create_if_missing=True,
        make_parents=True,
        unlink_first=False,
        line_ending=b"\n",
        comment_marker=comment_marker.encode("utf8", errors="strict"),
        ignore_leading_whitespace=ignore_leading_whitespace,
        ignore_trailing_whitespace=True,
    )
