import errno
import fcntl
import io
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from typing import cast
from unittest import mock

import pytest
from filetool import locked_file_handle
from filetool import open_eintr_safe


@contextmanager
# pylint: disable=missing-raises-doc  # W9006
def locked_file_handle_orig(
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

    """

    if create:
        # flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        # Must use O_RDWR here for some platforms: later re-open expects 'rb+' (read/write)
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        try:
            fd = open_eintr_safe(path, flags) # todo: 0o600? # fmt: skip
            os.close(fd)
        except FileExistsError:
            pass

    is_binary = "b" in mode
    assert is_binary  # for this program # fmt: skip
    fh = cast(BinaryIO, open(path, mode, encoding=None if is_binary else "utf-8"))
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
                        "Locking unavailable (ENOLCK). This may indicate NFSv3 with nolock or misconfigured lockd."
                    ) from e
                raise
    except Exception:
        fh.close()
        raise

    try:
        yield fh
    finally:

        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            print(f"Warning: failed to unlock file: {e}", file=sys.stderr)
            raise
        finally:
            fh.close()


# pylint: enable=missing-raises-doc

