import fcntl
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from filetool.filetool import _directory_lock
from filetool.filetool import _locked_file_handle


def _probe_file_lock(path: str, q: multiprocessing.Queue) -> None:
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        q.put("blocked")
        return
    finally:
        os.close(fd)
    q.put("acquired")


def _probe_directory_lock(directory: str, q: multiprocessing.Queue) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        q.put("blocked")
        return
    finally:
        os.close(fd)
    q.put("acquired")


def _probe(target, arg: str) -> str:
    q: multiprocessing.Queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=target, args=(arg, q))
    p.start()
    result = q.get(timeout=5)
    p.join(timeout=5)
    return result


def test_locked_file_handle_reads_and_writes(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"original\n")
    with _locked_file_handle(path=path, create=False) as fh:
        assert fh.read() == b"original\n"
        fh.write(b"locked\n")
    assert path.read_bytes() == b"original\nlocked\n"


def test_locked_file_handle_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        with _locked_file_handle(path=tmp_path / "missing", create=False):
            pass


def test_locked_file_handle_creates_when_create_true(tmp_path: Path):
    path = tmp_path / "new"
    with _locked_file_handle(path=path, create=True) as fh:
        fh.write(b"created\n")
    assert path.read_bytes() == b"created\n"


def test_locked_file_handle_excludes_other_process(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"x\n")
    with _locked_file_handle(path=path, create=False):
        assert _probe(_probe_file_lock, str(path)) == "blocked"
    assert _probe(_probe_file_lock, str(path)) == "acquired"


def test_locked_file_handle_releases_on_exception(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"x\n")
    with pytest.raises(RuntimeError):
        with _locked_file_handle(path=path, create=False):
            raise RuntimeError("boom")
    assert _probe(_probe_file_lock, str(path)) == "acquired"


def test_directory_lock_excludes_other_process(tmp_path: Path):
    with _directory_lock(tmp_path) as fd:
        assert os.fstat(fd).st_ino == tmp_path.stat().st_ino
        assert _probe(_probe_directory_lock, str(tmp_path)) == "blocked"
    assert _probe(_probe_directory_lock, str(tmp_path)) == "acquired"


def test_directory_lock_missing_directory_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        with _directory_lock(tmp_path / "missing"):
            pass


def _hold_directory_lock(directory: str, q: multiprocessing.Queue) -> None:
    with _directory_lock(Path(directory)):
        q.put("locked")
        time.sleep(0.5)


def test_directory_lock_blocks_until_released(tmp_path: Path):
    q: multiprocessing.Queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_hold_directory_lock, args=(str(tmp_path), q))
    p.start()
    assert q.get(timeout=5) == "locked"
    t0 = time.monotonic()
    with _directory_lock(tmp_path):
        waited = time.monotonic() - t0
    p.join(timeout=5)
    assert waited >= 0.4
