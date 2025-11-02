#!/usr/bin/env python3
"""
Tests for ensure_line_in_config_file function.
"""

from pathlib import Path

import pytest

from filetool.filetool import ensure_line_in_config_file


def test_ensure_line_creates_file_if_missing(tmp_path):
    """Test that ensure_line_in_config_file creates file if it doesn't exist."""
    config_file = tmp_path / "subdir" / "config.txt"

    ensure_line_in_config_file(
        path=config_file,
        line="export FOO=bar",
        comment_marker="#",
        ignore_leading_whitespace=True,
    )

    assert config_file.exists()
    assert config_file.read_text() == "export FOO=bar\n"


def test_ensure_line_adds_line_if_not_present(tmp_path):
    """Test that ensure_line_in_config_file adds line if not present."""
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\nline2\n")

    ensure_line_in_config_file(
        path=config_file,
        line="line3",
        comment_marker="#",
        ignore_leading_whitespace=True,
    )

    assert config_file.read_text() == "line1\nline2\nline3\n"


def test_ensure_line_does_not_duplicate_if_present(tmp_path):
    """Test that ensure_line_in_config_file doesn't duplicate existing line."""
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\nline2\nline3\n")

    ensure_line_in_config_file(
        path=config_file,
        line="line2",
        comment_marker="#",
        ignore_leading_whitespace=True,
    )

    # Should not add duplicate
    assert config_file.read_text() == "line1\nline2\nline3\n"


def test_ensure_line_with_inline_comments(tmp_path):
    """Test that ensure_line_in_config_file ignores inline comments when checking uniqueness."""
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\nline2 # inline comment\nline3\n")

    ensure_line_in_config_file(
        path=config_file,
        line="line2",
        comment_marker="#",
    )

    # Should not add duplicate because "line2 # inline comment" matches "line2" when ignoring comments
    assert config_file.read_text() == "line1\nline2 # inline comment\nline3\n"


def test_ensure_line_ignores_leading_whitespace(tmp_path):
    """Test that ensure_line_in_config_file ignores leading whitespace."""
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\n  line2\nline3\n")

    ensure_line_in_config_file(
        path=config_file,
        line="line2",
        comment_marker="#",
        ignore_leading_whitespace=True,
    )

    # Should not add duplicate (line2 exists with leading spaces)
    assert config_file.read_text() == "line1\n  line2\nline3\n"


def test_ensure_line_creates_parent_directories(tmp_path):
    """Test that ensure_line_in_config_file creates parent directories."""
    config_file = tmp_path / "a" / "b" / "c" / "config.txt"

    ensure_line_in_config_file(
        path=config_file,
        line="export PATH=/usr/bin",
        comment_marker="#",
        ignore_leading_whitespace=True,
    )

    assert config_file.exists()
    assert config_file.read_text() == "export PATH=/usr/bin\n"


def test_ensure_line_with_custom_comment_marker(tmp_path):
    """Test that ensure_line_in_config_file works with custom comment marker for inline comments."""
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\nline2 // inline comment\nline3\n")

    ensure_line_in_config_file(
        path=config_file,
        line="line2",
        comment_marker="//",
    )

    # Should not add duplicate because "line2 // inline comment" matches "line2" when ignoring comments
    assert config_file.read_text() == "line1\nline2 // inline comment\nline3\n"



def test_ensure_line_multiple_calls_idempotent(tmp_path):
    """Test that multiple calls to ensure_line_in_config_file are idempotent."""
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\n")

    # Call three times
    for _ in range(3):
        ensure_line_in_config_file(
            path=config_file,
            line="line2",
            comment_marker="#",
            ignore_leading_whitespace=True,
        )

    # Should only have one line2
    assert config_file.read_text() == "line1\nline2\n"
