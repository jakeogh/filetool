#!/usr/bin/env python3
"""
Test suite for ensure_bytes_present parameter validation.

Tests the constraint validation logic without requiring actual file operations.
"""

import tempfile
from pathlib import Path

import pytest
from filetool import ensure_bytes_present


def make_kwargs(**overrides):
    """Create a minimal valid argument set, overridden as needed."""
    base = dict(
        path=Path("/tmp/example.txt"),
        bytes_payload=b"line\n",
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
    """Test that empty bytes_payload is rejected."""
    with pytest.raises(ValueError, match="bytes_payload must not be empty"):
        ensure_bytes_present(**make_kwargs(bytes_payload=b""))


def test_line_ending_requires_unique_bytes():
    """Test that line_ending requires unique_bytes=True."""
    with pytest.raises(ValueError, match="line_ending requires unique_bytes=True"):
        ensure_bytes_present(**make_kwargs(line_ending=b"\n", unique_bytes=False))


def test_unique_bytes_with_line_ending_works():
    """Test that unique_bytes=True with line_ending works (line mode)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        path.write_bytes(b"existing\n")

        # This should work - line mode
        result = ensure_bytes_present(
            path=path,
            bytes_payload=b"newline\n",
            unique_bytes=True,
            create_if_missing=True,
            make_parents=False,
            line_ending=b"\n",
            comment_marker=None,
            ignore_leading_whitespace=False,
            ignore_trailing_whitespace=False,
        )

        assert result == 8  # "newline\n"
        assert path.read_bytes() == b"existing\nnewline\n"


def test_unique_bytes_without_line_ending_works():
    """Test that unique_bytes=True with line_ending=None works (binary mode)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"\xff\xfe\xfd")

        # This should work - binary substring search mode
        result = ensure_bytes_present(
            path=path,
            bytes_payload=b"\xaa\xbb",
            unique_bytes=True,
            create_if_missing=True,
            make_parents=False,
            line_ending=None,  # Binary mode
            comment_marker=None,
            ignore_leading_whitespace=False,
            ignore_trailing_whitespace=False,
        )

        assert result == 2  # Written
        assert path.read_bytes() == b"\xff\xfe\xfd\xaa\xbb"


def test_line_ending_not_empty_when_set():
    """Test that line_ending cannot be empty bytes when set."""
    with pytest.raises(ValueError, match="line_ending must not be empty if set"):
        ensure_bytes_present(**make_kwargs(unique_bytes=True, line_ending=b""))


def test_make_parents_requires_create_if_missing():
    """Test that make_parents=True requires create_if_missing=True."""
    with pytest.raises(
        ValueError, match="make_parents=True requires create_if_missing=True"
    ):
        ensure_bytes_present(**make_kwargs(make_parents=True, create_if_missing=False))


def test_comment_marker_must_be_bytes_or_none():
    """Test that comment_marker must be bytes or None."""
    with pytest.raises(
        TypeError, match=r"comment_marker must be of type .*bytes.*NoneType.*"
    ):
        ensure_bytes_present(
            **make_kwargs(
                comment_marker="not_bytes", unique_bytes=True, line_ending=b"\n"
            )
        )


def test_comment_marker_not_empty_if_set():
    """Test that comment_marker cannot be empty bytes when set."""
    with pytest.raises(ValueError, match=r"comment_marker must not be empty if set"):
        ensure_bytes_present(
            **make_kwargs(comment_marker=b"", unique_bytes=True, line_ending=b"\n")
        )


def test_comment_marker_requires_unique_bytes():
    """Test that comment_marker requires unique_bytes=True."""
    with pytest.raises(ValueError, match="comment_marker requires unique_bytes=True"):
        ensure_bytes_present(
            **make_kwargs(comment_marker=b"#", unique_bytes=False, line_ending=None)
        )


def test_comment_marker_not_equal_to_line_ending():
    """Test that comment_marker cannot equal line_ending."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        path.write_bytes(b"")

        with pytest.raises(ValueError, match="comment_marker can not match delim"):
            ensure_bytes_present(
                path=path,
                bytes_payload=b"test\n",
                comment_marker=b"#",
                line_ending=b"#",
                unique_bytes=True,
                create_if_missing=True,
                make_parents=False,
                ignore_leading_whitespace=False,
                ignore_trailing_whitespace=False,
            )


def test_ignore_leading_requires_unique_bytes():
    """Test that ignore_leading_whitespace requires unique_bytes=True."""
    with pytest.raises(
        ValueError, match=r"ignore_leading_whitespace=True requires unique_bytes=True"
    ):
        ensure_bytes_present(**make_kwargs(ignore_leading_whitespace=True))


def test_ignore_trailing_requires_unique_bytes():
    """Test that ignore_trailing_whitespace requires unique_bytes=True."""
    with pytest.raises(
        ValueError, match=r"ignore_trailing_whitespace=True requires unique_bytes=True"
    ):
        ensure_bytes_present(**make_kwargs(ignore_trailing_whitespace=True))


def test_comment_marker_requires_line_ending():
    """Test that comment_marker requires line_ending to be set (line mode only)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        path.write_bytes(b"")

        # Comment marker without line_ending should fail (no binary mode with comments)
        with pytest.raises(
            ValueError, match="comment_marker requires unique_bytes=True"
        ):
            ensure_bytes_present(
                path=path,
                bytes_payload=b"test",
                comment_marker=b"#",
                line_ending=None,
                unique_bytes=False,
                create_if_missing=True,
                make_parents=False,
                ignore_leading_whitespace=False,
                ignore_trailing_whitespace=False,
            )


def test_whitespace_flags_work_with_line_ending():
    """Test that whitespace flags work properly in line mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        path.write_bytes(b"  hello  \n")

        # Should match because whitespace is ignored
        result = ensure_bytes_present(
            path=path,
            bytes_payload=b"hello\n",
            unique_bytes=True,
            create_if_missing=True,
            make_parents=False,
            line_ending=b"\n",
            comment_marker=None,
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        assert result == 0  # Not written, already exists
        assert path.read_bytes() == b"  hello  \n"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
