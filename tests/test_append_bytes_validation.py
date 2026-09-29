#!/usr/bin/env python3
"""
Tests for validation errors in append_bytes_to_file.
"""

import pytest

from filetool import append_bytes_to_file


def test_empty_data_raises_error(tmp_path):
    """Test that appending empty bytes raises ValidationError."""
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"existing content")

    with pytest.raises(ValueError, match="Data must not be empty"):
        append_bytes_to_file(
            data=b"",
            path=test_file,
        )


def test_unlink_first_without_create_raises_error(tmp_path):
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"existing content")

    with pytest.raises(
        ValueError, match="unlink_first=True requires create_if_missing=True"
    ):
        append_bytes_to_file(
            data=b"new data",
            path=test_file,
            unlink_first=True,
            create_if_missing=False,
        )


def test_make_parents_without_create_raises_error(tmp_path):
    """Test that make_parents=True without create_if_missing=True raises ValidationError."""
    test_file = tmp_path / "subdir" / "test.bin"

    with pytest.raises(
        ValueError, match="make_parents=True requires create_if_missing=True"
    ):
        append_bytes_to_file(
            data=b"new data",
            path=test_file,
            make_parents=True,
            create_if_missing=False,
        )


def test_unlink_first_succeeds(tmp_path):
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"old content")

    result = append_bytes_to_file(
        data=b"new data",
        path=test_file,
        unlink_first=True,
    )

    assert result == 8  # len(b"new data")
    assert test_file.read_bytes() == b"new data"


def test_make_parents_with_create_succeeds(tmp_path):
    """Test that make_parents=True with create_if_missing=True works correctly."""
    test_file = tmp_path / "subdir" / "test.bin"

    result = append_bytes_to_file(
        data=b"new data",
        path=test_file,
        make_parents=True,
        create_if_missing=True,
    )

    assert result == 8
    assert test_file.read_bytes() == b"new data"
