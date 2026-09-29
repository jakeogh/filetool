import os
import stat
from pathlib import Path

import pytest

from filetool.filetool import _append_bytes_to_file


def make_kwargs(**overrides):
    base = dict(
        path=Path("/nonexistent/example.txt"),
        bytes_payload=b"line\n",
        unlink_first=False,
        unique_bytes=False,
        create_if_missing=False,
        make_parents=False,
        line_ending=None,
        comment_marker=None,
        ignore_leading_whitespace=False,
        ignore_trailing_whitespace=False,
    )
    base.update(overrides)
    return base


def test_bytes_payload_not_empty():
    with pytest.raises(ValueError, match="bytes_payload must not be empty"):
        _append_bytes_to_file(**make_kwargs(bytes_payload=b""))


def test_bytes_payload_must_be_bytes():
    with pytest.raises(TypeError, match="bytes_payload must be of type"):
        _append_bytes_to_file(**make_kwargs(bytes_payload="text"))


def test_path_must_be_path():
    with pytest.raises(TypeError, match="path must be of type"):
        _append_bytes_to_file(**make_kwargs(path="/tmp/x"))


@pytest.mark.parametrize(
    "flag",
    [
        "unlink_first",
        "unique_bytes",
        "create_if_missing",
        "make_parents",
        "ignore_leading_whitespace",
        "ignore_trailing_whitespace",
    ],
)
def test_bool_flags_must_be_bool(flag):
    with pytest.raises(TypeError, match=f"{flag} must be of type"):
        _append_bytes_to_file(**make_kwargs(**{flag: "yes"}))


def test_line_ending_not_empty_when_set():
    with pytest.raises(ValueError, match="line_ending must not be empty if set"):
        _append_bytes_to_file(**make_kwargs(line_ending=b""))


def test_line_ending_must_be_bytes_or_none():
    with pytest.raises(TypeError, match="line_ending must be of type"):
        _append_bytes_to_file(**make_kwargs(line_ending="\n"))


def test_make_parents_requires_create_if_missing():
    with pytest.raises(
        ValueError, match="make_parents=True requires create_if_missing=True"
    ):
        _append_bytes_to_file(**make_kwargs(make_parents=True, create_if_missing=False))


def test_unlink_first_requires_create_if_missing():
    with pytest.raises(
        ValueError, match="unlink_first=True requires create_if_missing=True"
    ):
        _append_bytes_to_file(**make_kwargs(unlink_first=True, create_if_missing=False))


def test_comment_marker_must_be_bytes_or_none():
    with pytest.raises(
        TypeError, match=r"comment_marker must be of type .*bytes.*NoneType"
    ):
        _append_bytes_to_file(
            **make_kwargs(comment_marker="#", unique_bytes=True, line_ending=b"\n")
        )


def test_comment_marker_not_empty_if_set():
    with pytest.raises(ValueError, match="comment_marker must not be empty if set"):
        _append_bytes_to_file(
            **make_kwargs(comment_marker=b"", unique_bytes=True, line_ending=b"\n")
        )


def test_comment_marker_requires_unique_bytes():
    with pytest.raises(ValueError, match="comment_marker requires unique_bytes=True"):
        _append_bytes_to_file(
            **make_kwargs(comment_marker=b"#", unique_bytes=False, line_ending=b"\n")
        )


def test_comment_marker_requires_line_ending():
    with pytest.raises(ValueError, match="require line_ending"):
        _append_bytes_to_file(
            **make_kwargs(comment_marker=b"#", unique_bytes=True, line_ending=None)
        )


@pytest.mark.parametrize(
    "flag", ["ignore_leading_whitespace", "ignore_trailing_whitespace"]
)
def test_whitespace_flags_require_unique_bytes(flag):
    with pytest.raises(ValueError, match=f"{flag}=True requires unique_bytes=True"):
        _append_bytes_to_file(**make_kwargs(**{flag: True, "line_ending": b"\n"}))


@pytest.mark.parametrize(
    "flag", ["ignore_leading_whitespace", "ignore_trailing_whitespace"]
)
def test_whitespace_flags_require_line_ending(flag):
    with pytest.raises(ValueError, match="require line_ending"):
        _append_bytes_to_file(**make_kwargs(**{flag: True, "unique_bytes": True}))


def test_comment_marker_may_not_contain_line_ending():
    with pytest.raises(
        ValueError, match="line_ending must not be contained in comment_marker"
    ):
        _append_bytes_to_file(
            **make_kwargs(comment_marker=b"#", line_ending=b"#", unique_bytes=True)
        )


def test_missing_file_without_create_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _append_bytes_to_file(**make_kwargs(path=tmp_path / "missing"))


def test_missing_parent_without_make_parents_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _append_bytes_to_file(
            **make_kwargs(path=tmp_path / "sub" / "f", create_if_missing=True)
        )


def test_create_if_missing_creates_file(tmp_path: Path):
    path = tmp_path / "new"
    n = _append_bytes_to_file(**make_kwargs(path=path, create_if_missing=True))
    assert n == 5
    assert path.read_bytes() == b"line\n"


def test_make_parents_creates_directories(tmp_path: Path):
    path = tmp_path / "a" / "b" / "f"
    n = _append_bytes_to_file(
        **make_kwargs(path=path, create_if_missing=True, make_parents=True)
    )
    assert n == 5
    assert path.read_bytes() == b"line\n"


def test_binary_append_is_verbatim(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    n = _append_bytes_to_file(**make_kwargs(path=path, bytes_payload=b"def"))
    assert n == 3
    assert path.read_bytes() == b"abcdef"


def test_line_mode_inserts_missing_separator(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"first")
    n = _append_bytes_to_file(
        **make_kwargs(path=path, bytes_payload=b"second\n", line_ending=b"\n")
    )
    assert n == 8
    assert path.read_bytes() == b"first\nsecond\n"


def test_line_mode_no_separator_when_terminated(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"first\n")
    n = _append_bytes_to_file(
        **make_kwargs(path=path, bytes_payload=b"second\n", line_ending=b"\n")
    )
    assert n == 7
    assert path.read_bytes() == b"first\nsecond\n"


def test_line_mode_no_separator_on_empty_file(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"")
    n = _append_bytes_to_file(
        **make_kwargs(path=path, bytes_payload=b"only\n", line_ending=b"\n")
    )
    assert n == 5
    assert path.read_bytes() == b"only\n"


def test_line_mode_separator_crlf(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"a\r\nb")
    n = _append_bytes_to_file(
        **make_kwargs(path=path, bytes_payload=b"c\r\n", line_ending=b"\r\n")
    )
    assert n == 5
    assert path.read_bytes() == b"a\r\nb\r\nc\r\n"


def test_unique_line_mode_skips_present_line(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"existing\n")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path, bytes_payload=b"existing\n", unique_bytes=True, line_ending=b"\n"
        )
    )
    assert n == 0
    assert path.read_bytes() == b"existing\n"


def test_unique_line_mode_matches_unterminated_final_line(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"first\nsecond")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path, bytes_payload=b"second\n", unique_bytes=True, line_ending=b"\n"
        )
    )
    assert n == 0
    assert path.read_bytes() == b"first\nsecond"


def test_unique_line_mode_appends_new_line(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"existing\n")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path, bytes_payload=b"newline\n", unique_bytes=True, line_ending=b"\n"
        )
    )
    assert n == 8
    assert path.read_bytes() == b"existing\nnewline\n"


def test_unique_line_mode_whitespace_normalization(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"  hello  \n")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path,
            bytes_payload=b"hello\n",
            unique_bytes=True,
            line_ending=b"\n",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )
    )
    assert n == 0
    assert path.read_bytes() == b"  hello  \n"


def test_unique_line_mode_comment_marker_strips_trailing_comment(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"hello # why\n")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path,
            bytes_payload=b"hello\n",
            unique_bytes=True,
            line_ending=b"\n",
            comment_marker=b"#",
            ignore_trailing_whitespace=True,
        )
    )
    assert n == 0


def test_unique_line_mode_commented_line_does_not_match(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"# hello\n")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path,
            bytes_payload=b"hello\n",
            unique_bytes=True,
            line_ending=b"\n",
            comment_marker=b"#",
        )
    )
    assert n == 6
    assert path.read_bytes() == b"# hello\nhello\n"


def test_unique_binary_mode_uses_substring_search(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"\xff\xfe\xfd")
    n = _append_bytes_to_file(
        **make_kwargs(path=path, bytes_payload=b"\xfe\xfd", unique_bytes=True)
    )
    assert n == 0
    n = _append_bytes_to_file(
        **make_kwargs(path=path, bytes_payload=b"\xaa\xbb", unique_bytes=True)
    )
    assert n == 2
    assert path.read_bytes() == b"\xff\xfe\xfd\xaa\xbb"


def test_unlink_first_replaces_content(tmp_path: Path):
    path = tmp_path / "f"
    path.write_bytes(b"old content\n")
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path, bytes_payload=b"new\n", unlink_first=True, create_if_missing=True
        )
    )
    assert n == 4
    assert path.read_bytes() == b"new\n"


def test_unlink_first_on_missing_file(tmp_path: Path):
    path = tmp_path / "f"
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path, bytes_payload=b"new\n", unlink_first=True, create_if_missing=True
        )
    )
    assert n == 4
    assert path.read_bytes() == b"new\n"


def test_unlink_first_with_make_parents(tmp_path: Path):
    path = tmp_path / "a" / "f"
    n = _append_bytes_to_file(
        **make_kwargs(
            path=path,
            bytes_payload=b"new\n",
            unlink_first=True,
            create_if_missing=True,
            make_parents=True,
        )
    )
    assert n == 4
    assert path.read_bytes() == b"new\n"


def test_symlink_target_is_written(tmp_path: Path):
    real = tmp_path / "real"
    real.write_bytes(b"a\n")
    link = tmp_path / "link"
    link.symlink_to(real)
    _append_bytes_to_file(**make_kwargs(path=link, bytes_payload=b"b\n"))
    assert link.is_symlink()
    assert real.read_bytes() == b"a\nb\n"


def test_no_stray_files_after_append(tmp_path: Path):
    path = tmp_path / "f"
    _append_bytes_to_file(**make_kwargs(path=path, create_if_missing=True))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f"]


def test_created_file_mode_respects_umask(tmp_path: Path):
    path = tmp_path / "f"
    old = os.umask(0o027)
    try:
        _append_bytes_to_file(**make_kwargs(path=path, create_if_missing=True))
    finally:
        os.umask(old)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
