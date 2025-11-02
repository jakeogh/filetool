#!/usr/bin/env python3
"""
Tests for remaining edge cases to improve coverage to 85%+.

This file combines tests for:
- CLI error handling
- splitlines_bytes edge cases
- Low-level exception handlers in filetool.py
"""

import pytest
import os
from pathlib import Path
from io import BytesIO
from filetool.cli import cli
from filetool.splitlines_bytes import splitlines_bytes
from filetool.filetool import find_bytes_offset_in_stream, _open_with_mode
from click.testing import CliRunner


# =============================================================================
# CLI Error Handling Tests
# =============================================================================

def test_cli_append_line_no_lines():
    """Test that append-line with no LINE arguments raises error."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['append-line', '--path', 'test.txt'])

        assert result.exit_code != 0
        assert "At least one LINE must be specified" in result.output


def test_cli_append_bytes_no_args():
    """Test that append-bytes with no arguments raises error."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['append-bytes', '--path', 'test.txt'])

        assert result.exit_code != 0
        assert "At least one of BYTES or --bytes-from-path must be specified" in result.output


def test_cli_append_bytes_both_args():
    """Test that append-bytes with both BYTES and --bytes-from-path raises error."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path('source.bin').write_bytes(b"data")

        result = runner.invoke(cli, [
            'append-bytes',
            '--path', 'test.bin',
            '--bytes-from-path', 'source.bin',
            'extra_bytes'
        ])

        assert result.exit_code != 0
        assert "BYTES and --bytes-from-path are mutually exclusive" in result.output


def test_cli_append_bytes_empty_input():
    """Test that append-bytes with empty input raises error."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, [
            'append-bytes',
            '--path', 'test.bin',
            ''
        ])

        assert result.exit_code != 0
        assert "Cannot write empty input" in result.output


def test_cli_append_bytes_invalid_hex():
    """Test that append-bytes with invalid hex input raises error."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, [
            'append-bytes',
            '--path', 'test.bin',
            '--hex-input',
            'ZZZZ'  # Invalid hex
        ])

        assert result.exit_code != 0
        assert "Invalid input" in result.output


def test_cli_append_bytes_from_missing_file():
    """Test that append-bytes with missing --bytes-from-path raises error."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, [
            'append-bytes',
            '--path', 'test.bin',
            '--bytes-from-path', 'nonexistent.bin'
        ])

        assert result.exit_code != 0
        assert "Failed to read" in result.output


# =============================================================================
# splitlines_bytes Edge Cases
# =============================================================================

def test_splitlines_delim_in_comment_marker_raises_error():
    """Test that delim contained in comment_marker raises ValueError."""
    data = b"line1\nline2\n"

    with pytest.raises(ValueError, match="delim must not be contained in comment_marker"):
        list(splitlines_bytes(
            data,
            delim=b"#",
            comment_marker=b"##",  # Contains delim
        ))


def test_splitlines_empty_delim_raises_error():
    """Test that empty delim raises ValueError."""
    data = b"line1\nline2\n"

    with pytest.raises(ValueError, match="delim must not be empty"):
        list(splitlines_bytes(data, delim=b""))


def test_splitlines_empty_comment_marker_raises_error():
    """Test that empty comment_marker raises ValueError."""
    data = b"line1\nline2\n"

    with pytest.raises(ValueError, match="comment_marker must not be empty"):
        list(splitlines_bytes(data, delim=b"\n", comment_marker=b""))


def test_splitlines_comment_marker_equals_delim_raises_error():
    """Test that comment_marker == delim raises ValueError."""
    data = b"line1\nline2\n"

    with pytest.raises(ValueError, match="comment_marker can not match delim"):
        list(splitlines_bytes(data, delim=b"#", comment_marker=b"#"))


def test_splitlines_non_bytes_comment_marker_raises_error():
    """Test that non-bytes comment_marker raises TypeError."""
    data = b"line1\nline2\n"

    with pytest.raises(TypeError, match="comment_marker must be bytes or None"):
        list(splitlines_bytes(data, delim=b"\n", comment_marker="#"))


def test_splitlines_with_stream():
    """Test splitlines_bytes with BinaryIO stream."""
    data = b"line1\nline2\nline3\n"
    stream = BytesIO(data)

    result = list(splitlines_bytes(stream, delim=b"\n"))

    assert result == [b"line1\n", b"line2\n", b"line3\n"]


def test_splitlines_stream_with_small_chunks():
    """Test splitlines_bytes with small chunk_size."""
    data = b"line1\nline2\nline3\n"
    stream = BytesIO(data)

    result = list(splitlines_bytes(stream, delim=b"\n", chunk_size=3))

    assert result == [b"line1\n", b"line2\n", b"line3\n"]


# =============================================================================
# find_bytes_offset_in_stream Tests
# =============================================================================

def test_find_bytes_offset_empty_target_raises_error():
    """Test that find_bytes_offset_in_stream with empty target raises ValueError."""
    stream = BytesIO(b"some data")

    with pytest.raises(ValueError, match="Target bytes must not be empty"):
        find_bytes_offset_in_stream(stream, target=b"")


def test_find_bytes_offset_not_found():
    """Test that find_bytes_offset_in_stream returns None when target not found."""
    stream = BytesIO(b"some data here")

    result = find_bytes_offset_in_stream(stream, target=b"notfound")

    assert result is None


def test_find_bytes_offset_at_start():
    """Test that find_bytes_offset_in_stream finds target at start."""
    stream = BytesIO(b"target data here")

    result = find_bytes_offset_in_stream(stream, target=b"target")

    assert result == 0


def test_find_bytes_offset_at_end():
    """Test that find_bytes_offset_in_stream finds target at end."""
    stream = BytesIO(b"some data target")

    result = find_bytes_offset_in_stream(stream, target=b"target")

    assert result == 10


def test_find_bytes_offset_in_middle():
    """Test that find_bytes_offset_in_stream finds target in middle."""
    stream = BytesIO(b"some target data")

    result = find_bytes_offset_in_stream(stream, target=b"target")

    assert result == 5


def test_find_bytes_offset_across_chunks():
    """Test that find_bytes_offset_in_stream finds target spanning chunks."""
    # Target spans across chunk boundary
    data = b"a" * 100 + b"TARGET" + b"b" * 100
    stream = BytesIO(data)

    result = find_bytes_offset_in_stream(stream, target=b"TARGET", chunk_size=50)

    assert result == 100


def test_find_bytes_offset_with_overlap():
    """Test that find_bytes_offset_in_stream handles overlapping patterns."""
    stream = BytesIO(b"aaaa" + b"target" + b"bbbb")

    result = find_bytes_offset_in_stream(stream, target=b"target", chunk_size=3)

    assert result == 4


# =============================================================================
# _open_with_mode Tests
# =============================================================================

def test_open_with_mode_creates_file_with_permissions(tmp_path):
    """Test that _open_with_mode creates file with specified permissions."""
    test_file = tmp_path / "test.txt"

    # Create file with specific permissions
    fd = _open_with_mode(
        test_file,
        os.O_CREAT | os.O_WRONLY,
        0o644,
    )

    try:
        # Verify file was created
        assert test_file.exists()

        # Verify permissions (mask out file type bits)
        stat_info = test_file.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o644
    finally:
        os.close(fd)


def test_open_with_mode_respects_umask(tmp_path):
    """Test that _open_with_mode properly handles umask."""
    test_file = tmp_path / "test.txt"

    # Save old umask
    old_umask = os.umask(0o022)

    try:
        fd = _open_with_mode(
            test_file,
            os.O_CREAT | os.O_WRONLY,
            0o666,
        )

        os.close(fd)

        # With umask 0o022, 0o666 should become 0o644
        # But _open_with_mode sets umask to 0 temporarily, so we get exact mode
        stat_info = test_file.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o666
    finally:
        # Restore umask
        os.umask(old_umask)


# =============================================================================
# Exception Handler Coverage Tests
# =============================================================================

def test_comment_out_line_wrong_types(tmp_path):
    """Test type validation in comment_out_line_in_file."""
    from filetool import comment_out_line_in_file

    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    # Wrong path type
    with pytest.raises(TypeError, match="path must be Path"):
        comment_out_line_in_file(path="string", line="line1")

    # Wrong line type
    with pytest.raises(TypeError, match="line must be str"):
        comment_out_line_in_file(path=test_file, line=123)

    # Wrong comment_marker type
    with pytest.raises(TypeError, match="comment_marker must be str"):
        comment_out_line_in_file(path=test_file, line="line1", comment_marker=123)

    # Wrong line_ending type
    with pytest.raises(TypeError, match="line_ending must be bytes"):
        comment_out_line_in_file(path=test_file, line="line1", line_ending="\n")


def test_uncomment_line_wrong_types(tmp_path):
    """Test type validation in uncomment_line_in_file."""
    from filetool import uncomment_line_in_file

    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    # Wrong path type
    with pytest.raises(TypeError, match="path must be Path"):
        uncomment_line_in_file(path="string", line="line1")

    # Wrong line type
    with pytest.raises(TypeError, match="line must be str"):
        uncomment_line_in_file(path=test_file, line=123)

    # Wrong comment_marker type
    with pytest.raises(TypeError, match="comment_marker must be str"):
        uncomment_line_in_file(path=test_file, line="line1", comment_marker=123)

    # Wrong line_ending type
    with pytest.raises(TypeError, match="line_ending must be bytes"):
        uncomment_line_in_file(path=test_file, line="line1", line_ending="\n")

    # Wrong multiple type
    with pytest.raises(TypeError, match="multiple must be bool"):
        uncomment_line_in_file(path=test_file, line="line1", multiple="yes")


def test_ensure_line_in_config_file_with_line_ending_raises_error(tmp_path):
    """Test that ensure_line_in_config_file raises error if line contains line_ending."""
    from filetool.filetool import ensure_line_in_config_file

    test_file = tmp_path / "config.txt"

    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        ensure_line_in_config_file(
            path=test_file,
            line="line1\nline2",
            comment_marker="#",
        )


# =============================================================================
# Run Coverage Report After Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=filetool", "--cov-report=term-missing"])
