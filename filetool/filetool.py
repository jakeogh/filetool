#!/usr/bin/env python3
# tab-width:4

# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive(!)

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import random
import sys
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from typing import BinaryIO
from typing import cast

from .splitlines_bytes import splitlines_bytes

# from rich.traceback import install
# install(show_locals=True)

__all__ = [
    "_append_bytes_to_file",
    "_locked_file_handle",
    "splitlines_bytes",
    "_ensure_bytes_present",
    "ensure_line_in_config_file",
    "_open_eintr_safe",
    "comment_out_line_in_file",
]

Constraint = dict[str, Any]

DEFAULT_LOCK_DIR = Path("/tmp/filetool-locks")
LOCK_DIR = Path(os.environ.get("FILETOOL_LOCK_DIR", DEFAULT_LOCK_DIR))
LOCK_DIR.mkdir(
    parents=True,
    exist_ok=True,
    mode=0o700,
)


def _get_lockfile_path(target_path: Path) -> Path:
    canonical_path = str(target_path.resolve())
    digest = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()
    return LOCK_DIR / digest


def _fsync_eintr_safe(fd: int):
    while True:
        try:
            return os.fsync(fd)
        except OSError as e:
            if e.errno == errno.EINTR:
                continue
            raise


def _open_eintr_safe(*args, **kwargs):
    while True:
        try:
            return os.open(*args, **kwargs)
        except OSError as e:
            if e.errno == errno.EINTR:
                continue
            raise


def _open_with_mode(
    path: os.PathLike,
    flags: int,
    mode: int,
) -> int:
    old_umask = os.umask(0)
    try:
        return _open_eintr_safe(
            path,
            flags,
            mode,
        )
    finally:
        os.umask(old_umask)


@contextmanager
def _locked_file_handle(
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
        >>> with _locked_file_handle(Path("/tmp/data.bin"), mode="rb+") as fh:
        >>>     data = fh.read()
        >>>     fh.seek(0)
        >>>     fh.write(data + b"\n")

    Note:
        - This only applies file-level advisory locking via `fcntl.flock`.
        - To ensure inter-process correctness, this is typically used *alongside a global per-path lockfile* (see `_ensure_bytes_present()`).
        - Guarantees release of lock even if close() fails.
        - Escalates via os.close(fileno()) if necessary.
        - Emits warnings instead of silently failing on unlock/close.
    """
    if create:
        # flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        # Must use O_RDWR here for some platforms: later re-open expects 'rb+' (read/write)
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        try:
            fd = _open_eintr_safe(path, flags)
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


@contextmanager
def _safe_open_rw_binary(
    path: Path,
    *,
    require_exists: bool,
) -> Iterator[BinaryIO]:
    """
    Open a file in 'rb+' mode, atomically creating it if it doesn't exist,
    and acquire an advisory exclusive lock.

    This wraps `_locked_file_handle()` and ensures the file exists beforehand,
    avoiding race conditions with concurrent creators.

    - If the file exists: opens in 'rb+' without altering timestamps.
    - If the file doesn't exist: creates it atomically with 'xb' mode.
    - If another process wins the race to create the file: reopens it safely.

    Yields:
        BinaryIO: A file object locked and opened in 'rb+' mode.
    """
    try:
        with _locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=False,
        ) as fh:
            yield fh
    except FileNotFoundError:
        if require_exists:
            raise
        with _locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=True,
        ) as fh:
            yield fh


def _validate_args(
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


def _ensure_bytes_present(
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
        - If `line_ending` is None (binary mode):
            - Performs binary substring search using `find_bytes_offset_in_stream()`.
            - Only appends `bytes_payload` if the exact byte sequence is not found anywhere in the file.
            - Note: `comment_marker`, `ignore_leading_whitespace`, and `ignore_trailing_whitespace`
              have no effect when `line_ending=None` (binary mode).

    Uniqueness semantics:
        - With `line_ending`: Line-oriented comparison (is this line already present?)
        - Without `line_ending`: Substring search (does this byte sequence appear anywhere?)

        This distinction is intentional: line mode checks logical presence of lines,
        while binary mode checks physical presence of byte sequences within the file.

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

    _validate_args(
        function_name="_ensure_bytes_present",
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
    lock_path = _get_lockfile_path(path)
    # without 0o666 the root user might create a lockfile that the normal user cant acquire a lock on.
    lock_fd = _open_with_mode(
        lock_path,
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o666,
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        with _locked_file_handle(
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
            _fsync_eintr_safe(fh.fileno())
            return len(bytes_payload)
    finally:
        os.close(lock_fd)


def _append_bytes_to_file(
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
    or checks for its presence using line-by-line comparison (when `line_ending` is provided)
    or binary substring search (when `line_ending` is None) before appending.
    It supports advisory locking, atomic creation, and optional directory creation.
    Input must be raw bytes; no encoding or decoding is performed.

    Parameters:
        bytes_payload (bytes): The byte sequence to append. Must not be empty.
        path (Path): The target file to append to.
        unlink_first (bool): If True, unlink the file before writing. Requires `unique_bytes=True`.
        unique_bytes (bool): If True, do not append if the payload is already present.
        create_if_missing (bool): If True, create the file if it doesn't exist.
        make_parents (bool): If True, create parent directories if needed. Requires `create_if_missing=True`.
        line_ending (bytes | None): Logical line ending used for line-based deduplication. Requires `unique_bytes=True`.
        comment_marker (bytes | None): Optional comment prefix to strip during deduplication. Requires `unique_bytes=True`.
        ignore_leading_whitespace (bool): Ignore leading whitespace when checking for uniqueness. Requires `unique_bytes=True`.
        ignore_trailing_whitespace (bool): Ignore trailing whitespace when checking for uniqueness. Requires `unique_bytes=True`.

    Uniqueness behavior when `unique_bytes=True`:
        - With `line_ending`: Performs line-by-line comparison. Each line in the file is compared
          to `bytes_payload` (which should include the line ending). Only appends if no matching line exists.
        - Without `line_ending`: Performs binary substring search. Appends only if `bytes_payload`
          is not found as a substring anywhere in the file.

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

    _validate_args(
        function_name="_append_bytes_to_file",
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
                _fsync_eintr_safe(fh.fileno())
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
        bytes_written = _ensure_bytes_present(
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
            # Use _safe_open_rw_binary to handle 'rb+' access race-safely:
            # - File may not exist yet (create it)
            # - Or it may exist already due to a race (open it safely)
            # - Either way, we may need to read it if a race created it already

            bytes_written = _ensure_bytes_present(
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
            bytes_written = _ensure_bytes_present(
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


def _modify_file_lines(
    *,
    path: Path,
    line_transformer: Callable[[bytes], bytes],
    line_ending: bytes,
) -> int:
    """
    Atomically read, transform, and rewrite a file line-by-line.

    INTERNAL FUNCTION - Not exposed in __all__. Provides the primitive for higher-level
    operations like comment_out_line_in_file().

    This function implements a read-modify-write pattern with the same locking guarantees
    as the append operations.

    Locking and atomicity guarantees:
        1. Acquires global per-file lock (SHA256-based lockfile in /tmp/filetool-locks)
        2. Acquires advisory flock() on the target file
        3. Records file inode before reading
        4. Verifies inode unchanged after reading (detects replacement during read)
        5. Writes transformed content to temporary file in same directory
        6. Uses hardlink to detect replacement in critical rename window
        7. Atomically renames temporary file over original
        8. Preserves file permissions and ownership

    File replacement detection strategy:
        - Before reading: Record original inode
        - After reading: Verify inode unchanged (catches replacement during read phase)
        - Before rename: Create hardlink and verify link count (catches replacement in
          the microsecond window between final check and rename)

    The hardlink trick closes the race window:
        If the file is replaced after we create the hardlink, the hardlink still points
        to the old inode, but path.stat() returns the new inode with link count 1.
        We detect this mismatch and abort the operation.

    Filesystem compatibility:
        - Works on modern Linux filesystems
        - Gracefully falls back to best-effort rename on vfat, exfat etc.
        - May have issues on CIFS/SMB with unreliable hardlink semantics

    Parameters:
        path (Path): File to modify. Must exist.
        line_transformer (Callable[[bytes], bytes]): Function that transforms each line.
            Receives line WITH line_ending, must return line WITH line_ending.
            Return the same bytes to leave line unchanged.
        line_ending (bytes): Line delimiter. Typically b'\n', b'\r\n', or b'\r'.

    Returns:
        int: Number of lines that were actually modified (transformer returned different bytes).

    Raises:
        FileNotFoundError: If file doesn't exist
        OSError: If file is replaced during modification, or other I/O errors
        PermissionError: If insufficient permissions to read, write, or modify file

    Implementation notes:
        - Reads entire file into memory (not suitable for gigabyte-sized files)
        - Temporary file is written to same directory as target (ensures same filesystem)
        - Temporary file naming: .filetool.tmp.{pid}.{random}
        - Attempts to preserve permissions/ownership (ownership may fail if non-root)
        - Cleans up temporary file even if operation fails
    """

    if not isinstance(path, Path):
        raise TypeError(f"path must be Path, got {type(path).__name__}")
    if not isinstance(line_ending, bytes):
        raise TypeError(f"line_ending must be bytes, got {type(line_ending).__name__}")
    if len(line_ending) == 0:
        raise ValueError("line_ending must not be empty")
    if not callable(line_transformer):
        raise TypeError("line_transformer must be callable")

    # HOOK:step_1__get_lockfile_path
    # Acquire global lock to serialize access across all cooperating processes
    lock_path = _get_lockfile_path(path)
    # HOOK:step_2_open_lockfile
    lock_fd = _open_with_mode(
        lock_path,
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o666,  # Allow all users to acquire lock
    )

    try:
        # HOOK:step_3_acquire_global_lock
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # HOOK:step_4_stat_before
        # Record file metadata BEFORE opening
        # This establishes our baseline for detecting replacement
        try:
            stat_before = path.stat()
        except FileNotFoundError:
            raise FileNotFoundError(f"File does not exist: {path}")

        # HOOK:step_5_record_inode
        inode_before = stat_before.st_ino

        # HOOK:step_6_call__locked_file_handle
        # Open file with advisory lock
        with _locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=False,
        ) as fh:
            # HOOK:step_9_fstat_opened
            # Verify the file we opened is the same one we stat'd
            # This catches replacement between stat() and open()
            stat_opened = os.fstat(fh.fileno())
            # HOOK:step_10_compare_inode_after_open
            if stat_opened.st_ino != inode_before:
                raise OSError(
                    f"File {path} was replaced between stat and open "
                    f"(inode changed from {inode_before} to {stat_opened.st_ino})"
                )

            # HOOK:step_11_seek_to_start
            # Read and parse all lines
            fh.seek(0)
            # HOOK:step_12_read_lines
            lines = list(
                splitlines_bytes(
                    fh,
                    delim=line_ending,
                    comment_marker=None,
                    strip_leading_whitespace=False,
                    strip_trailing_whitespace=False,
                )
            )

            # HOOK:step_13_stat_after_read
            # Verify file still has same inode after reading
            # This catches replacement during the read phase
            try:
                stat_after_read = path.stat()
            except FileNotFoundError:
                raise OSError(f"File {path} was deleted during read operation")

            # HOOK:step_14_compare_inode_after_read
            if stat_after_read.st_ino != inode_before:
                raise OSError(
                    f"File {path} was replaced during read operation "
                    f"(inode changed from {inode_before} to {stat_after_read.st_ino})"
                )

            # HOOK:step_15_transform_lines
            # Transform lines and count modifications
            modified_count = 0
            new_lines: list[bytes] = []

            for line in lines:
                new_line = line_transformer(line)

                # Validate transformer output
                if not isinstance(new_line, bytes):
                    raise TypeError(
                        f"line_transformer must return bytes, got {type(new_line).__name__}"
                    )

                if new_line != line:
                    modified_count += 1

                new_lines.append(new_line)

            # HOOK:step_17_check_if_modified
            # If nothing changed, return early without writing
            if modified_count == 0:
                return 0

            # Generate temporary file path in same directory
            # Using same directory ensures atomic rename (same filesystem)
            temp_path = (
                path.parent
                / f".filetool.tmp.{os.getpid()}.{random.randint(100000, 999999)}"
            )
            # HOOK:step_18_generate_temp_path

            try:
                # HOOK:step_19_open_temp_file
                # Write transformed content to temporary file
                with open(temp_path, "xb") as temp_fh:
                    # HOOK:step_20_write_temp_file
                    for line in new_lines:
                        temp_fh.write(line)
                    # HOOK:step_21_flush_and_fsync
                    temp_fh.flush()
                    _fsync_eintr_safe(temp_fh.fileno())

                # HOOK:step_23_chmod_temp
                # Copy permissions from original file
                os.chmod(temp_path, stat_before.st_mode)

                # HOOK:step_24_chown_temp
                # Attempt to copy ownership (may fail if not root)
                try:
                    os.chown(
                        temp_path,
                        stat_before.st_uid,
                        stat_before.st_gid,
                    )
                except PermissionError:
                    pass  # Non-root users can't chown, but that's acceptable

                # HOOK:step_25_stat_before_rename
                # CRITICAL SECTION: Verify file unchanged and perform atomic rename
                #
                # There's still a race window between this check and the rename.
                # We use the hardlink trick to detect replacement in that window.

                try:
                    stat_before_rename = path.stat()
                except FileNotFoundError:
                    # File was deleted - clean up and abort
                    temp_path.unlink()
                    raise OSError(f"File {path} was deleted before rename operation")

                # HOOK:step_26_compare_inode_before_rename
                if stat_before_rename.st_ino != inode_before:
                    # File was replaced - clean up and abort
                    temp_path.unlink()
                    raise OSError(
                        f"File {path} was replaced before rename operation "
                        f"(inode changed from {inode_before} to {stat_before_rename.st_ino})"
                    )

                # HOOK:step_27_generate_link_path
                # Hardlink trick: Create hardlink to detect replacement in rename window
                #
                # How this works:
                # 1. Create hardlink: both 'path' and 'link_path' point to same inode
                # 2. Original file now has link count = nlink + 1
                # 3. If someone replaces 'path', they create a NEW inode at that path
                # 4. The hardlink still points to the OLD inode
                # 5. When we stat('path'), we get the NEW inode with link count = 1
                # 6. We detect the mismatch and abort
                #
                # This closes the race window on filesystems with hardlink support.

                link_path = path.parent / f".filetool.link.{os.getpid()}"
                hardlink_successful = False
                hardlink_verification_failed = False
                hardlink_failed_inode = None
                hardlink_failed_nlink = None

                try:
                    # HOOK:step_28_create_hardlink
                    # Attempt to create hardlink
                    print(
                        f"[LEGIT] About to create hardlink, current nlink: {path.stat().st_nlink}"
                    )
                    os.link(path, link_path)
                    print(
                        f"[LEGIT] Created hardlink, new nlink: {path.stat().st_nlink}"
                    )

                    # HOOK:step_29_calculate_expected_link_count
                    expected_link_count = stat_before_rename.st_nlink + 1

                    # HOOK:step_30_stat_after_link
                    # Verify hardlink creation by checking link count
                    # We must stat 'path', not 'link_path', to detect replacement
                    stat_after_link = path.stat()
                    print(
                        f"[LEGIT] After attacker, stat_after_link.st_nlink = {stat_after_link.st_nlink}"
                    )
                    print(f"[LEGIT] expected_link_count = {expected_link_count}")

                    # HOOK:step_31_verify_hardlink
                    if (
                        stat_after_link.st_nlink == expected_link_count
                        and stat_after_link.st_ino == inode_before
                    ):
                        # HOOK:step_32_hardlink_successful
                        # Hardlink successful and file still unchanged
                        hardlink_successful = True
                    else:
                        # Hardlink verification failed - file was modified concurrently
                        # Store details for error reporting outside this try block
                        hardlink_verification_failed = True
                        hardlink_failed_inode = stat_after_link.st_ino
                        hardlink_failed_nlink = stat_after_link.st_nlink

                except (OSError, PermissionError):
                    # Filesystem doesn't support hardlinks (vfat, exfat) or permission denied
                    # Fall through to regular rename (best effort)
                    if link_path.exists():
                        try:
                            link_path.unlink()
                        except:
                            pass

                # Check if hardlink verification failed - must be outside try-except
                # so our OSError doesn't get caught by the filesystem support handler
                if hardlink_verification_failed:
                    # Clean up hardlink and temp file
                    try:
                        link_path.unlink()
                    except FileNotFoundError:
                        pass
                    try:
                        temp_path.unlink()
                    except FileNotFoundError:
                        pass

                    # Determine why it failed and raise appropriate error
                    if hardlink_failed_inode != inode_before:
                        raise OSError(
                            f"File {path} was replaced during hardlink verification "
                            f"(inode changed from {inode_before} to {hardlink_failed_inode})"
                        )
                    else:
                        raise OSError(
                            f"File {path} was modified during operation "
                            f"(link count mismatch: expected {expected_link_count}, got {hardlink_failed_nlink})"
                        )

                # HOOK:step_33_rename
                # Perform atomic rename
                # If hardlink is present, the inode check above ensures correctness
                # If hardlink failed, we do best-effort rename with small race window
                os.rename(temp_path, path)

                # HOOK:step_34_cleanup_hardlink
                # Clean up hardlink if it exists
                if hardlink_successful:
                    try:
                        link_path.unlink()
                    except FileNotFoundError:
                        pass  # Already cleaned up or race occurred

                return modified_count

            except Exception:
                # Clean up temporary file on any error
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
                raise

    finally:
        # HOOK:step_36_close_lockfile
        os.close(lock_fd)


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
    Comment out all occurrences of a line in a file.

    This function searches for exact matches of the specified line and prepends
    the comment marker to each matching line. All matches are commented out atomically
    in a single operation with full locking guarantees.

    Typical use case: Toggle configuration lines in config files on/off.

    Atomicity guarantees:
        - Uses same global locking as append operations
        - Detects file replacement via inode checking
        - Uses hardlink trick to prevent race conditions
        - All changes applied atomically via write-to-temp + rename

    Parameters:
        path (Path): Path to the file to modify. Must exist.
        line (str): The line content to comment out (without line ending or comment marker).
                    For example: "export FOO=bar" not "# export FOO=bar\n"
        comment_marker (str): Comment prefix to add. Default: "#"
                             A space is automatically added after the marker.
        line_ending (bytes): Line ending delimiter. Default: b"\n" (LF)
                            Common values: b"\n" (Unix), b"\r\n" (Windows), b"\r" (Mac Classic)
        ignore_leading_whitespace (bool): If True, ignore leading whitespace when matching lines.
                                         Example: "  export FOO=bar" matches "export FOO=bar"
        ignore_trailing_whitespace (bool): If True, ignore trailing whitespace when matching lines.
                                          Example: "export FOO=bar  " matches "export FOO=bar"

    Returns:
        int: Number of lines that were commented out.
             Returns 0 if no matching lines were found or if all matches were already commented.

    Raises:
        FileNotFoundError: If the file doesn't exist
        OSError: If file is replaced during modification or other I/O errors
        PermissionError: If insufficient permissions
        ValueError: If line contains the line_ending delimiter
        TypeError: If parameters have wrong types

    Example:
        # Comment out all export statements for FOO
        count = comment_out_line_in_file(
            path=Path("/etc/environment"),
            line="export FOO=bar",
            comment_marker="#",
        )
        print(f"Commented out {count} lines")

        # File before:
        # export PATH=/usr/bin
        # export FOO=bar
        # export BAR=baz
        # export FOO=bar
        #
        # File after:
        # export PATH=/usr/bin
        # # export FOO=bar
        # export BAR=baz
        # # export FOO=bar

    Notes:
        - Lines already starting with comment marker (even with whitespace) will NOT match
        - Whitespace handling is only applied to the matching logic, not to the original line
        - Comment marker + space is prepended to the ORIGINAL line (preserves original formatting)
        - This is a line-oriented operation; partial line matches are not supported
        - Uses same locking mechanism as append operations (cooperating processes only)
    """

    # Parameter validation
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

    # Encode for byte-level operations
    line_bytes = line.encode("utf-8", errors="strict")
    comment_prefix = (comment_marker + " ").encode("utf-8", errors="strict")

    # Check that line doesn't contain line_ending
    # This prevents ambiguity and ensures line-oriented matching
    if line_ending in line_bytes:
        raise ValueError(
            f"line contains the line_ending delimiter ({line_ending!r}). "
            f"This function operates on single lines only. "
            f"Use separate calls for multiple lines or choose a different line_ending."
        )

    # Build target pattern: line + line_ending
    target = line_bytes + line_ending

    # Define the transformer function
    # This will be called for each line in the file
    def transformer(line_with_ending: bytes) -> bytes:
        # Build comparison line respecting whitespace options
        compare_line = line_with_ending

        if ignore_leading_whitespace:
            # Strip leading whitespace but preserve line_ending
            stripped = compare_line.lstrip()
            if stripped == line_ending or len(stripped) == 0:
                # Line is only whitespace
                compare_line = line_ending
            else:
                compare_line = stripped

        if ignore_trailing_whitespace:
            # Strip trailing whitespace but preserve line_ending
            if compare_line.endswith(line_ending):
                content = compare_line[: -len(line_ending)]
                compare_line = content.rstrip() + line_ending
            else:
                compare_line = compare_line.rstrip()

        # Check if this line matches our target
        if compare_line == target:
            # Match found - prepend comment marker to ORIGINAL line
            # We comment the original to preserve formatting
            return comment_prefix + line_with_ending
        else:
            # No match - return unchanged
            return line_with_ending

    # Perform the atomic modification
    return _modify_file_lines(
        path=path,
        line_transformer=transformer,
        line_ending=line_ending,
    )


def ensure_line_in_config_file(
    *,
    path: Path,
    line: str,
    comment_marker: str,
    ignore_leading_whitespace: bool,
):

    _bytes = line.encode("utf8", errors="strict")
    _ = _append_bytes_to_file(
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
    Uncomment one or all occurrences of a commented line in a file.

    This function searches for lines that match the specified line content
    (when the comment marker is removed) and removes the comment marker from
    matching lines. All changes are applied atomically in a single operation
    with full locking guarantees.

    Typical use case: Re-enable configuration lines that were previously
    commented out.

    Atomicity guarantees:
        - Uses same global locking as append operations
        - Detects file replacement via inode checking
        - Uses hardlink trick to prevent race conditions
        - All changes applied atomically via write-to-temp + rename

    Parameters:
        path (Path): Path to the file to modify. Must exist.
        line (str): The line content to uncomment (without line ending or comment marker).
                    For example: "export FOO=bar" not "# export FOO=bar\n"
        comment_marker (str): Comment prefix to remove. Default: "#"
                             The function expects "# " (marker + space) before the line.
        line_ending (bytes): Line ending delimiter. Default: b"\n" (LF)
        ignore_leading_whitespace (bool): If True, ignore leading whitespace when matching lines.
        ignore_trailing_whitespace (bool): If True, ignore trailing whitespace when matching lines.
        multiple (bool): If False (default), uncomment only the first occurrence.
                        If True, uncomment all occurrences.

    Returns:
        int: Number of lines that were uncommented.
             Returns 0 if line exists but is already uncommented (idempotent behavior).

    Raises:
        ValueError: If the line is not found in the file (neither commented nor uncommented)
        FileNotFoundError: If the file doesn't exist
        OSError: If file is replaced during modification or other I/O errors
        PermissionError: If insufficient permissions
        TypeError: If parameters have wrong types

    Example:
        # Uncomment the first FOO export
        count = uncomment_line_in_file(
            path=Path("/etc/environment"),
            line="export FOO=bar",
            comment_marker="#",
        )
        print(f"Uncommented {count} lines")

        # File before:
        # export PATH=/usr/bin
        # # export FOO=bar
        # export BAR=baz
        # # export FOO=bar
        #
        # File after (multiple=False):
        # export PATH=/usr/bin
        # export FOO=bar
        # export BAR=baz
        # # export FOO=bar

        # File after (multiple=True):
        # export PATH=/usr/bin
        # export FOO=bar
        # export BAR=baz
        # export FOO=bar

    Notes:
        - Lines without the comment marker will NOT be modified
        - Whitespace handling is only applied to matching logic
        - The uncommented line preserves its original formatting
        - This is a line-oriented operation; partial line matches are not supported
        - Uses same locking mechanism as append operations (cooperating processes only)
        - Idempotent: if line is already uncommented, returns 0 with no error
    """

    # Parameter validation
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
    if not isinstance(multiple, bool):
        raise TypeError(f"multiple must be bool, got {type(multiple).__name__}")

    if len(line) == 0:
        raise ValueError("line must not be empty")
    if len(comment_marker) == 0:
        raise ValueError("comment_marker must not be empty")
    if len(line_ending) == 0:
        raise ValueError("line_ending must not be empty")

    # Encode for byte-level operations
    line_bytes = line.encode("utf-8", errors="strict")
    comment_prefix = (comment_marker + " ").encode("utf-8", errors="strict")

    # Check that line doesn't contain line_ending
    if line_ending in line_bytes:
        raise ValueError(
            f"line contains the line_ending delimiter ({line_ending!r}). "
            f"This function operates on single lines only. "
            f"Use separate calls for multiple lines or choose a different line_ending."
        )

    # Build target patterns
    target_uncommented = line_bytes + line_ending
    target_commented = comment_prefix + line_bytes + line_ending

    # Track what we find
    found_uncommented = False
    found_commented = False
    uncommented_count = 0

    # Define the transformer function
    def transformer(line_with_ending: bytes) -> bytes:
        nonlocal found_uncommented, found_commented, uncommented_count

        # Build comparison line respecting whitespace options
        compare_line = line_with_ending

        if ignore_leading_whitespace:
            # Strip leading whitespace but preserve line_ending
            stripped = compare_line.lstrip()
            if stripped == line_ending or len(stripped) == 0:
                # Line is only whitespace
                compare_line = line_ending
            else:
                compare_line = stripped

        if ignore_trailing_whitespace:
            # Strip trailing whitespace but preserve line_ending
            if compare_line.endswith(line_ending):
                content = compare_line[: -len(line_ending)]
                compare_line = content.rstrip() + line_ending
            else:
                compare_line = compare_line.rstrip()

        # Check if line matches (uncommented version)
        if compare_line == target_uncommented:
            found_uncommented = True
            return line_with_ending  # Already uncommented, no change

        # Check if line matches (commented version)
        if compare_line == target_commented:
            found_commented = True
            # If multiple=False and we already uncommented one, leave the rest
            if not multiple and uncommented_count > 0:
                return line_with_ending
            # Uncomment this line by removing the comment prefix
            uncommented_count += 1
            return line_bytes + line_ending

        # No match - return unchanged
        return line_with_ending

    # Perform the atomic modification
    _modify_file_lines(
        path=path,
        line_transformer=transformer,
        line_ending=line_ending,
    )

    # Post-operation validation
    if not found_uncommented and not found_commented:
        raise ValueError(
            f"Line not found in file: {line!r}. "
            f"The line must exist (either commented or uncommented) to use this function."
        )

    # If line exists but is already uncommented, that's fine - goal achieved
    # Return 0 to indicate no changes were needed (idempotent behavior)
    return uncommented_count
