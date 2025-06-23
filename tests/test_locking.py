import errno
import fcntl
import io
import multiprocessing
import os
import shutil
import sys
import tempfile
import time
from multiprocessing import Process
from multiprocessing import Queue
from pathlib import Path
from unittest import mock

import pytest
from filetool import locked_file_handle



import pytest
from filetool import locked_file_handle
from locked_file_handle_orig import locked_file_handle_orig

@pytest.mark.parametrize("which_fn,should_raise", [
    (locked_file_handle_orig, True),
    (locked_file_handle, False),
])
def test_locked_file_unlock_fails_param(which_fn, tmp_path, capsys, should_raise):
    path = tmp_path / "unlockfail.txt"
    path.write_bytes(b"unlock test\n")

    with mock.patch("fcntl.flock") as flock_mock:

        def flock_side_effect(fd, operation):
            if operation in (fcntl.LOCK_EX, fcntl.LOCK_EX | fcntl.LOCK_NB):
                return 0  # Simulate success
            elif operation == fcntl.LOCK_UN:
                raise OSError(errno.EPERM, "Simulated unlock failure")
            raise RuntimeError("Unexpected flock operation")

        flock_mock.side_effect = flock_side_effect

        if should_raise:
            with pytest.raises(OSError, match="Simulated unlock failure"):
                with which_fn(path=path, mode="rb+", blocking=True, create=False) as fh:
                    fh.write(b"closing soon\n")
        else:
            with which_fn(path=path, mode="rb+", blocking=True, create=False) as fh:
                fh.write(b"closing soon\n")

            captured = capsys.readouterr()
            assert "Warning: failed to unlock file" in captured.err
            assert "Simulated unlock failure" in captured.err



# exposed bug in new locked_file_handle implementaton
def test_locked_file_raises_oserror_enolck(tmp_path):
    path = tmp_path / "enolck.txt"
    path.write_bytes(b"x\n")

    # Patch fcntl.flock to raise ENOLCK
    with mock.patch("fcntl.flock") as flock_mock:
        flock_mock.side_effect = OSError(errno.ENOLCK, "No locks available")

        with pytest.raises(OSError) as exc_info:
            with locked_file_handle(path=path, mode="rb+", blocking=True, create=False):
                pass  # will not reach here

        assert "ENOLCK" in str(exc_info.value)
        assert "lockd" in str(exc_info.value) or "nolock" in str(exc_info.value)


def test_locked_file_allows_exclusive_access(tmp_path):
    path = tmp_path / "locktest1"
    path.write_bytes(b"original\n")

    with locked_file_handle(path=path, mode="rb+", blocking=True, create=False) as fh:
        data = fh.read()
        assert b"original" in data
        fh.seek(0, os.SEEK_END)
        fh.write(b"locked\n")

    # Check that write succeeded
    assert b"locked\n" in path.read_bytes()


def try_lock_nonblocking(path: str, q):
    try:
        with locked_file_handle(
            path=Path(path), mode="rb+", blocking=False, create=False
        ):
            q.put("acquired")
    except BlockingIOError:
        q.put("blocked")


def test_locked_file_blocks_other_access(tmp_path):
    path = tmp_path / "locktest2"
    path.write_bytes(b"first\n")

    with locked_file_handle(path=path, mode="rb+", blocking=True, create=False):
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=try_lock_nonblocking, args=(str(path), q))
        p.start()
        p.join(timeout=2)
        assert q.get(timeout=1) == "blocked"


def test_locked_file_allows_access_after_release(tmp_path):
    path = tmp_path / "locktest3"
    path.write_bytes(b"init\n")

    with locked_file_handle(path=path, mode="rb+", blocking=True, create=False):
        pass  # acquire and release immediately

    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=try_lock_nonblocking, args=(str(path), q))
    p.start()
    p.join(timeout=2)
    assert q.get(timeout=1) == "acquired"


def test_locked_file_creates_when_create_true(tmp_path):
    path = tmp_path / "autocreate.bin"
    assert not path.exists()

    with locked_file_handle(path=path, mode="rb+", blocking=True, create=True) as fh:
        fh.write(b"created\n")

    assert path.exists()
    assert path.read_bytes() == b"created\n"


def test_locked_file_raises_blockingioerror(tmp_path):
    path = tmp_path / "locktest4"
    path.write_bytes(b"x\n")

    with locked_file_handle(path=path, mode="rb+", blocking=True, create=False):
        with pytest.raises(BlockingIOError):
            with locked_file_handle(
                path=path, mode="rb+", blocking=False, create=False
            ):
                pass  # won't reach


@pytest.fixture
def temp_file():
    dirpath = tempfile.mkdtemp()
    path = Path(dirpath) / "locktest.bin"
    path.write_bytes(b"initial\n")
    yield path
    shutil.rmtree(dirpath)


def test_basic_lock_write(temp_file):
    with locked_file_handle(
        path=temp_file,
        mode="rb+",
        blocking=True,
        create=False,
    ) as fh:
        data = fh.read()
        fh.seek(0, os.SEEK_END)
        fh.write(b"appended\n")

    contents = temp_file.read_bytes()
    assert contents.endswith(b"appended\n")


def test_lock_blocks_when_held(temp_file):
    queue = Queue()

    def hold_lock(path, q):
        with locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=False,
        ):
            q.put("locked")
            time.sleep(1)

    p = Process(target=hold_lock, args=(temp_file, queue))
    p.start()
    assert queue.get(timeout=1) == "locked"

    t0 = time.time()
    with locked_file_handle(
        path=temp_file,
        mode="rb+",
        blocking=True,
        create=False,
    ) as fh:
        t1 = time.time()

    p.join()
    assert (t1 - t0) >= 0.8  # Allow small timing variation


def test_lock_nonblocking_failure(temp_file):
    def hold_lock(path):
        with locked_file_handle(
            path=path,
            mode="rb+",
            blocking=True,
            create=False,
        ):
            time.sleep(1)

    p = Process(target=hold_lock, args=(temp_file,))
    p.start()
    time.sleep(0.1)  # Give time for subprocess to acquire lock

    with pytest.raises(BlockingIOError):
        with locked_file_handle(
            path=temp_file, mode="rb+", blocking=False, create=False
        ):
            pass

    p.join()


def test_unlock_on_exit(temp_file):
    with locked_file_handle(
        path=temp_file,
        mode="rb+",
        blocking=True,
        create=False,
    ) as fh:
        fh.write(b"check\n")

    # Should be immediately acquirable again
    with locked_file_handle(
        path=temp_file,
        mode="rb+",
        blocking=True,
        create=False,
    ) as fh2:
        content = fh2.read()
    assert b"check\n" in content
