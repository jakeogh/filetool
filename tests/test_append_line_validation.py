#!/usr/bin/env python3
"""
Tests for validation errors in append_line_to_file.
"""

import pytest

from filetool import append_line_to_file


def test_empty_line_raises_error(tmp_path):
    """Test that appending empty line raises ValidationError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("existing line\n")

    with pytest.raises(ValueError, match="Line must not be empty"):
        append_line_to_file(
            line="",
            path=test_file,
        )


def test_unlink_first_without_create_raises_error(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("existing line\n")

    with pytest.raises(
        ValueError, match="unlink_first=True requires create_if_missing=True"
    ):
        append_line_to_file(
            line="new line",
            path=test_file,
            unlink_first=True,
            create_if_missing=False,
        )


def test_comment_marker_without_unique_raises_error(tmp_path):
    test_file = tmp_path / "test.txt"
    with pytest.raises(ValueError, match="comment_marker requires unique=True"):
        append_line_to_file(line="x", path=test_file, comment_marker="#")


def test_unlink_first_does_not_require_unique(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("old\n")
    assert append_line_to_file(line="new", path=test_file, unlink_first=True) == 4
    assert test_file.read_bytes() == b"new\n"


def test_missing_trailing_newline_gets_separator(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"first")
    assert append_line_to_file(line="second", path=test_file) == 8
    assert test_file.read_bytes() == b"first\nsecond\n"


def test_unique_matches_unterminated_final_line(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"first\nsecond")
    assert append_line_to_file(line="second", path=test_file, unique=True) == 0
    assert test_file.read_bytes() == b"first\nsecond"


def test_make_parents_without_create_raises_error(tmp_path):
    """Test that make_parents=True without create_if_missing=True raises ValidationError."""
    test_file = tmp_path / "subdir" / "test.txt"

    with pytest.raises(
        ValueError, match="make_parents=True requires create_if_missing=True"
    ):
        append_line_to_file(
            line="new line",
            path=test_file,
            make_parents=True,
            create_if_missing=False,
        )


def test_ignore_leading_whitespace_without_unique_raises_error(tmp_path):
    """Test that ignore_leading_whitespace=True without unique=True raises ValidationError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("existing line\n")

    with pytest.raises(
        ValueError, match="ignore_leading_whitespace=True requires unique=True"
    ):
        append_line_to_file(
            line="new line",
            path=test_file,
            ignore_leading_whitespace=True,
            unique=False,
        )


def test_ignore_trailing_whitespace_without_unique_raises_error(tmp_path):
    """Test that ignore_trailing_whitespace=True without unique=True raises ValidationError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("existing line\n")

    with pytest.raises(
        ValueError, match="ignore_trailing_whitespace=True requires unique=True"
    ):
        append_line_to_file(
            line="new line",
            path=test_file,
            ignore_trailing_whitespace=True,
            unique=False,
        )


def test_line_contains_line_ending_raises_error(tmp_path):
    """Test that line containing line_ending raises ValidationError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("existing line\n")

    with pytest.raises(ValueError, match="Line contains the line_ending delimiter"):
        append_line_to_file(
            line="line1\nline2",
            path=test_file,
        )


def test_whitespace_flags_with_unique_succeed(tmp_path):
    """Test that whitespace flags work correctly with unique=True."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("  existing line  \n")

    # Should not append because line already exists (ignoring whitespace)
    result = append_line_to_file(
        line="existing line",
        path=test_file,
        unique=True,
        ignore_leading_whitespace=True,
        ignore_trailing_whitespace=True,
    )

    assert result == 0
