import os
import stat
from pathlib import Path

import pytest

from filetool.filetool import _modify_file_lines


def upper(line: bytes) -> bytes:
    return line.upper()


def identity(line: bytes) -> bytes:
    return line


def test_transforms_lines_and_returns_count(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\nB\nc\n")
    n = _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert n == 2
    assert path.read_bytes() == b"A\nB\nC\n"


def test_unterminated_final_line_round_trips(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\nb")
    n = _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert n == 2
    assert path.read_bytes() == b"A\nB"


def test_custom_line_ending(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\r\nb\r\n")
    n = _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\r\n")
    assert n == 2
    assert path.read_bytes() == b"A\r\nB\r\n"


def test_no_change_leaves_file_untouched(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\nb\n")
    before = path.stat()
    n = _modify_file_lines(path=path, line_transformer=identity, line_ending=b"\n")
    assert n == 0
    after = path.stat()
    assert after.st_ino == before.st_ino
    assert after.st_mtime_ns == before.st_mtime_ns


def test_empty_file(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"")
    assert _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n") == 0
    assert path.read_bytes() == b""


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _modify_file_lines(
            path=tmp_path / "missing", line_transformer=upper, line_ending=b"\n"
        )


def test_transformer_returning_non_bytes_raises_and_leaves_file(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    with pytest.raises(TypeError, match="line_transformer must return bytes"):
        _modify_file_lines(
            path=path, line_transformer=lambda line: "A\n", line_ending=b"\n"
        )
    assert path.read_bytes() == b"a\n"
    assert [p.name for p in tmp_path.iterdir()] == ["f"]


def test_transformer_exception_cleans_temp_file(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\nb\n")
    calls = 0

    def explode(line: bytes) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boom")
        return line.upper()

    with pytest.raises(RuntimeError):
        _modify_file_lines(path=path, line_transformer=explode, line_ending=b"\n")
    assert path.read_bytes() == b"a\nb\n"
    assert [p.name for p in tmp_path.iterdir()] == ["f"]


def test_preserves_mode(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    path.chmod(0o640)
    _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_replaces_inode_and_leaves_no_temp_files(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    before = path.stat().st_ino
    _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert path.stat().st_ino != before
    assert [p.name for p in tmp_path.iterdir()] == ["f"]


def test_symlink_target_is_rewritten_and_link_survives(tmp_path: Path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real = real_dir / "conf"
    real.write_bytes(b"a\n")
    link = tmp_path / "link"
    link.symlink_to(real)
    n = _modify_file_lines(path=link, line_transformer=upper, line_ending=b"\n")
    assert n == 1
    assert link.is_symlink()
    assert real.read_bytes() == b"A\n"
    assert [p.name for p in real_dir.iterdir()] == ["conf"]


def test_dangling_symlink_raises(tmp_path: Path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "gone")
    with pytest.raises(FileNotFoundError):
        _modify_file_lines(path=link, line_transformer=upper, line_ending=b"\n")


def test_replacement_between_stat_and_open_is_detected(tmp_path: Path, monkeypatch):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    original_stat = Path.stat
    calls = 0

    def replacing_stat(self, *args, **kwargs):
        nonlocal calls
        result = original_stat(self, *args, **kwargs)
        if self == path:
            calls += 1
            if calls == 1:
                tmp = tmp_path / "attacker"
                tmp.write_bytes(b"attacker\n")
                os.rename(tmp, path)
        return result

    monkeypatch.setattr(Path, "stat", replacing_stat)
    with pytest.raises(OSError, match="replaced between stat and open"):
        _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert path.read_bytes() == b"attacker\n"
    assert [p.name for p in tmp_path.iterdir()] == ["f"]


def test_replacement_before_rename_is_detected(tmp_path: Path, monkeypatch):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    original_stat = Path.stat
    calls = 0

    def replacing_stat(self, *args, **kwargs):
        nonlocal calls
        if self == path:
            calls += 1
            if calls == 2:
                tmp = tmp_path / "attacker"
                tmp.write_bytes(b"attacker\n")
                os.rename(tmp, path)
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", replacing_stat)
    with pytest.raises(OSError, match="replaced before rename"):
        _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert path.read_bytes() == b"attacker\n"
    assert [p.name for p in tmp_path.iterdir()] == ["f"]


def test_deletion_before_rename_aborts(tmp_path: Path, monkeypatch):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    original_stat = Path.stat
    calls = 0

    def deleting_stat(self, *args, **kwargs):
        nonlocal calls
        if self == path:
            calls += 1
            if calls == 2:
                path.unlink()
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", deleting_stat)
    with pytest.raises(FileNotFoundError):
        _modify_file_lines(path=path, line_transformer=upper, line_ending=b"\n")
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "kwargs, exc, msg",
    [
        ({"path": "f"}, TypeError, "path must be Path"),
        ({"line_ending": "\n"}, TypeError, "line_ending must be bytes"),
        ({"line_ending": b""}, ValueError, "line_ending must not be empty"),
        ({"line_transformer": 42}, TypeError, "line_transformer must be callable"),
    ],
)
def test_argument_validation(tmp_path: Path, kwargs, exc, msg):
    path = tmp_path / "f"
    path.write_bytes(b"a\n")
    full = {"path": path, "line_transformer": upper, "line_ending": b"\n"}
    full.update(kwargs)
    with pytest.raises(exc, match=msg):
        _modify_file_lines(**full)
