#!/usr/bin/env python3
"""
Test unique_bytes=True with line_ending=None (binary substring mode).

This tests the binary substring search functionality when unique_bytes is enabled
but line_ending is not specified.
"""

import tempfile
from pathlib import Path

import pytest
from filetool import append_bytes_to_file


def test_append_bytes_to_file_unique_bytes_binary_mode_skip_existing():
    """unique_bytes=True with line_ending=None should skip if bytes exist anywhere in file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"\xff\xfe\xfd\xfc")

        # Should not append because bytes already exist (binary substring search)
        result = append_bytes_to_file(
            bytes_payload=b"\xfe\xfd",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written, already exists
        assert path.read_bytes() == b"\xff\xfe\xfd\xfc"


def test_append_bytes_to_file_unique_bytes_binary_mode_append_new():
    """unique_bytes=True with line_ending=None should append if bytes don't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"\xff\xfe\xfd\xfc")

        # Should append because these bytes don't exist
        result = append_bytes_to_file(
            bytes_payload=b"\xaa\xbb",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 2  # Written
        assert path.read_bytes() == b"\xff\xfe\xfd\xfc\xaa\xbb"


def test_append_bytes_to_file_unique_bytes_binary_mode_exact_match():
    """unique_bytes=True with line_ending=None should skip if exact content exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"hello world")

        # Should not append because exact content already exists
        result = append_bytes_to_file(
            bytes_payload=b"hello world",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written
        assert path.read_bytes() == b"hello world"


def test_append_bytes_to_file_unique_bytes_binary_mode_substring_match():
    """unique_bytes=True with line_ending=None should skip if substring exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"prefix_TARGET_suffix")

        # Should not append because TARGET already exists as substring
        result = append_bytes_to_file(
            bytes_payload=b"TARGET",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written
        assert path.read_bytes() == b"prefix_TARGET_suffix"


def test_append_bytes_to_file_unique_bytes_binary_mode_at_start():
    """unique_bytes=True with line_ending=None should detect match at file start."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"START_rest_of_file")

        # Should not append because START is at beginning
        result = append_bytes_to_file(
            bytes_payload=b"START",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written
        assert path.read_bytes() == b"START_rest_of_file"


def test_append_bytes_to_file_unique_bytes_binary_mode_at_end():
    """unique_bytes=True with line_ending=None should detect match at file end."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"beginning_of_file_END")

        # Should not append because END is at end
        result = append_bytes_to_file(
            bytes_payload=b"END",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written
        assert path.read_bytes() == b"beginning_of_file_END"


def test_append_bytes_to_file_unique_bytes_binary_mode_empty_file():
    """unique_bytes=True with line_ending=None should append to empty file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"")

        # Should append because file is empty
        result = append_bytes_to_file(
            bytes_payload=b"first content",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 13  # Written
        assert path.read_bytes() == b"first content"


def test_append_bytes_to_file_unique_bytes_binary_mode_null_bytes():
    """unique_bytes=True with line_ending=None should handle null bytes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"\x00\x01\x02\x03\x00\x00")

        # Should not append because null bytes already exist
        result = append_bytes_to_file(
            bytes_payload=b"\x00\x00",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written
        assert path.read_bytes() == b"\x00\x01\x02\x03\x00\x00"


def test_append_bytes_to_file_unique_bytes_binary_mode_similar_but_different():
    """unique_bytes=True with line_ending=None should append if similar but not exact."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"hello world")

        # Should append because "hello_world" is different from "hello world"
        result = append_bytes_to_file(
            bytes_payload=b"hello_world",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 11  # Written
        assert path.read_bytes() == b"hello worldhello_world"


def test_append_bytes_to_file_unique_bytes_binary_mode_multiple_occurrences():
    """unique_bytes=True with line_ending=None should skip even if substring appears multiple times."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.bin"
        path.write_bytes(b"AAA_BBB_AAA_CCC")

        # Should not append because AAA already exists (even though it appears twice)
        result = append_bytes_to_file(
            bytes_payload=b"AAA",
            path=path,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode
            create_if_missing=True,
            make_parents=False,
        )

        assert result == 0  # Not written
        assert path.read_bytes() == b"AAA_BBB_AAA_CCC"


def test_append_bytes_to_file_unique_bytes_binary_vs_line_mode():
    """Compare binary mode (line_ending=None) vs line mode (line_ending=b'\\n')."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Binary mode - should match substring anywhere
        path1 = Path(tmpdir) / "binary.txt"
        path1.write_bytes(b"prefix\nTARGET\nsuffix\n")

        result1 = append_bytes_to_file(
            bytes_payload=b"TARGET",
            path=path1,
            unlink_first=False,
            unique_bytes=True,
            line_ending=None,  # Binary mode - searches for substring
            create_if_missing=True,
            make_parents=False,
        )

        assert result1 == 0  # Found as substring, not written

        # Test 2: Line mode - should match because file contains "TARGET\n" as a complete line
        path2 = Path(tmpdir) / "line.txt"
        path2.write_bytes(b"prefix\nTARGET\nsuffix\n")

        result2 = append_bytes_to_file(
            bytes_payload=b"TARGET\n",
            path=path2,
            unlink_first=False,
            unique_bytes=True,
            line_ending=b"\n",  # Line mode - compares complete lines (including delimiter)
            create_if_missing=True,
            make_parents=False,
        )

        assert result2 == 0  # Found as complete line (with newline), not written
        assert path2.read_bytes() == b"prefix\nTARGET\nsuffix\n"

        # Test 3: Line mode - should NOT match if we search for line without newline
        path3 = Path(tmpdir) / "line2.txt"
        path3.write_bytes(b"prefix\nTARGET\nsuffix\n")

        result3 = append_bytes_to_file(
            bytes_payload=b"TARGET",  # Without newline
            path=path3,
            unlink_first=False,
            unique_bytes=True,
            line_ending=b"\n",  # Line mode
            create_if_missing=True,
            make_parents=False,
        )

        # This should append because "TARGET" != "TARGET\n" in line mode
        assert result3 == 6  # Written (but will get newline added? No, raw bytes)
        # Actually, checking the code - bytes_payload is written as-is in line mode too
        assert b"TARGET" in path3.read_bytes()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
