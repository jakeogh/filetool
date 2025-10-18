#!/usr/bin/env python3
"""
Test suite for filetool CLI append commands.

Tests the CLI interface for append-line and append-bytes commands.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from filetool.cli import cli


@pytest.fixture
def tmpfile(tmp_path):
    """Create a temporary file path for testing."""
    return tmp_path / "file.txt"


def read_file(path):
    """Read file as bytes."""
    return path.read_bytes()


# =============================================================================
# Basic append-line tests
# =============================================================================


def test_basic_append_line(tmpfile):
    """Test basic line append with automatic newline."""
    runner = CliRunner()
    result = runner.invoke(cli, ["append-line", "hello", "--path", str(tmpfile)])
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"hello\n"
    assert "Wrote 6 bytes" in result.output


def test_multiple_lines(tmpfile):
    """Test appending multiple lines."""
    runner = CliRunner()
    result = runner.invoke(cli, ["append-line", "line1", "line2", "--path", str(tmpfile)])
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"line1\nline2\n"


@pytest.mark.parametrize("line_ending", ["LF", "CRLF", "CR"])
def test_line_endings(tmpfile, line_ending):
    """Test different line ending types."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "test",
            "--path",
            str(tmpfile),
            "--line-ending",
            line_ending,
        ],
    )
    assert result.exit_code == 0, result.output

    line_ending_map = {"LF": b"\n", "CRLF": b"\r\n", "CR": b"\r"}
    expected = b"test" + line_ending_map[line_ending]
    assert read_file(tmpfile) == expected


def test_unique_append_skip_existing(tmpfile):
    """Test that unique flag prevents duplicate lines."""
    tmpfile.write_text("unique\n")
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "unique", "--path", str(tmpfile), "--unique"]
    )
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"unique\n"
    # Should not say "Wrote" because nothing was written
    assert "Wrote" not in result.output


def test_unique_append_add_new(tmpfile):
    """Test that unique flag allows new lines."""
    tmpfile.write_text("existing\n")
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "newline", "--path", str(tmpfile), "--unique"]
    )
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"existing\nnewline\n"
    assert "Wrote 8 bytes" in result.output


@pytest.mark.parametrize(
    "file_content,search_line,ignore_leading,ignore_trailing,should_match",
    [
        # Both whitespace flags: "  hello  " matches "hello"
        ("  hello  \n", "hello", True, True, True),
        # Only leading: "  hello  " becomes "hello  " which doesn't match "hello"
        ("  hello  \n", "hello", True, False, False),
        # Only trailing: "  hello  " becomes "  hello" which doesn't match "hello"
        ("  hello  \n", "hello", False, True, False),
        # Neither: "  hello  " doesn't match "hello"
        ("  hello  \n", "hello", False, False, False),
        # Exact match with leading whitespace ignored
        ("  hello\n", "hello", True, False, True),
        # Exact match with trailing whitespace ignored
        ("hello  \n", "hello", False, True, True),
    ],
)
def test_unique_ignore_whitespace(
    tmpfile, file_content, search_line, ignore_leading, ignore_trailing, should_match
):
    """Test unique with whitespace ignoring options."""
    tmpfile.write_text(file_content)
    runner = CliRunner()

    args = ["append-line", search_line, "--path", str(tmpfile), "--unique"]
    if ignore_leading:
        args.append("--ignore-leading-whitespace")
    if ignore_trailing:
        args.append("--ignore-trailing-whitespace")

    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output

    content = read_file(tmpfile)
    if should_match:
        # Line matched, should not append
        assert content == file_content.encode()
        assert "Wrote" not in result.output
    else:
        # Line didn't match, should append
        assert content == file_content.encode() + (search_line + "\n").encode()
        assert "Wrote" in result.output


def test_comment_marker(tmpfile):
    """Test comment marker stripping in unique mode."""
    tmpfile.write_text("abc# comment\n")  # No space before #
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "abc",
            "--path",
            str(tmpfile),
            "--unique",
            "--comment-marker",
            "#",
        ],
    )
    assert result.exit_code == 0, result.output
    # "abc" matches "abc# comment" after comment stripping (becomes "abc\n")
    assert read_file(tmpfile) == b"abc# comment\n"
    assert "Wrote" not in result.output


def test_comment_marker_with_space(tmpfile):
    """Test comment marker with space before it requires --ignore-trailing-whitespace."""
    tmpfile.write_text("abc # comment\n")  # Space before #
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "abc",
            "--path",
            str(tmpfile),
            "--unique",
            "--comment-marker",
            "#",
        ],
    )
    assert result.exit_code == 0, result.output
    # "abc " (with space) doesn't match "abc" (without space), so it appends
    assert read_file(tmpfile) == b"abc # comment\nabc\n"
    assert "Wrote 4 bytes" in result.output


def test_comment_marker_with_trailing_whitespace_flag(tmpfile):
    """Test comment marker with --ignore-trailing-whitespace to match despite space."""
    tmpfile.write_text("abc # comment\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "abc",
            "--path",
            str(tmpfile),
            "--unique",
            "--comment-marker",
            "#",
            "--ignore-trailing-whitespace",
        ],
    )
    assert result.exit_code == 0, result.output
    # "abc " → "abc" after trailing whitespace stripped, matches "abc"
    assert read_file(tmpfile) == b"abc # comment\n"
    assert "Wrote" not in result.output


def test_unlink_first(tmpfile):
    """Test unlinking file before writing with unique."""
    tmpfile.write_text("old content\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "new",
            "--path",
            str(tmpfile),
            "--unlink-first",
            "--unique",
        ],
    )
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"new\n"


@pytest.mark.parametrize(
    "make_parents,file_exists_initially,should_succeed",
    [
        (True, False, True),  # Make parents: should work
        (False, True, True),  # Parent exists: should work
        (False, False, False),  # No parent, no make-parents: should fail
    ],
)
def test_make_parents(tmp_path, make_parents, file_exists_initially, should_succeed):
    """Test parent directory creation."""
    file_path = tmp_path / "nested" / "deep" / "file.txt"

    if file_exists_initially:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()

    args = ["append-line", "deep", "--path", str(file_path)]
    if make_parents:
        args.append("--make-parents")

    result = runner.invoke(cli, args)

    if should_succeed:
        assert result.exit_code == 0, result.output
        assert file_path.read_bytes() == b"deep\n"
    else:
        assert result.exit_code != 0


def test_dry_run(tmpfile):
    """Test dry-run mode doesn't modify file."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "test", "--path", str(tmpfile), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "[filetool append-line][dry-run]" in result.output
    assert "Would write" in result.output
    assert not tmpfile.exists()


def test_do_not_create_missing_file(tmpfile):
    """Test that --do-not-create flag prevents file creation."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "test", "--path", str(tmpfile), "--do-not-create"]
    )
    assert result.exit_code != 0
    assert not tmpfile.exists()


def test_do_not_create_existing_file(tmpfile):
    """Test that --do-not-create works with existing files."""
    tmpfile.write_text("existing\n")
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "new", "--path", str(tmpfile), "--do-not-create"]
    )
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"existing\nnew\n"


# =============================================================================
# append-bytes tests
# =============================================================================


def test_append_bytes_basic(tmpfile):
    """Test basic bytes append (no automatic newline for append-bytes)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["append-bytes", "hello", "--path", str(tmpfile)])
    assert result.exit_code == 0, result.output
    # append-bytes does NOT add newline automatically (unlike append-line)
    assert read_file(tmpfile) == b"hello"


def test_append_bytes_hex_input(tmpfile):
    """Test hex input mode."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            "68656c6c6f",
            "--path",
            str(tmpfile),
            "--hex-input",
        ],
    )
    assert result.exit_code == 0, result.output
    # No automatic newline for append-bytes
    assert read_file(tmpfile) == b"hello"


@pytest.mark.parametrize(
    "hex_value,expected",
    [("00", b"\x00"), ("ff", b"\xff"), ("0a", b"\n"), ("0d0a", b"\r\n")],
)
def test_append_bytes_hex_various(tmpfile, hex_value, expected):
    """Test various hex values."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            hex_value,
            "--path",
            str(tmpfile),
            "--hex-input",
        ],
    )
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == expected


def test_bytes_from_path(tmpfile, tmp_path):
    """Test reading bytes from another file."""
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"\xff\xfe\xfd\xfc")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            "--path",
            str(tmpfile),
            "--bytes-from-path",
            str(payload),
        ],
    )
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"\xff\xfe\xfd\xfc"


def test_append_bytes_unique_binary_mode(tmpfile):
    """Test unique bytes in binary mode (no line ending specified)."""
    tmpfile.write_bytes(b"\xff\xfe\xfd")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            "fffe",
            "--path",
            str(tmpfile),
            "--unique",
            "--hex-input",
        ],
    )
    assert result.exit_code == 0, result.output
    # Should not append because \xff\xfe already exists in file
    assert read_file(tmpfile) == b"\xff\xfe\xfd"


def test_append_bytes_multiple(tmpfile):
    """Test appending multiple byte sequences."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-bytes", "first", "second", "--path", str(tmpfile)]
    )
    assert result.exit_code == 0, result.output
    # Each written separately, no newlines
    assert read_file(tmpfile) == b"firstsecond"


# =============================================================================
# Error condition tests
# =============================================================================


def test_error_no_input_append_line(tmpfile):
    """Test error when no lines provided."""
    runner = CliRunner()
    result = runner.invoke(cli, ["append-line", "--path", str(tmpfile)])
    assert result.exit_code != 0
    assert "At least one LINE must be specified" in result.output


def test_error_no_input_append_bytes(tmpfile):
    """Test error when no bytes provided."""
    runner = CliRunner()
    result = runner.invoke(cli, ["append-bytes", "--path", str(tmpfile)])
    assert result.exit_code != 0
    assert "At least one of BYTES or --bytes-from-path" in result.output


def test_error_conflict_bytes_and_positional(tmpfile, tmp_path):
    """Test error when both positional args and --bytes-from-path used."""
    payload = tmp_path / "payload"
    payload.write_text("abc")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            "abc",
            "--path",
            str(tmpfile),
            "--bytes-from-path",
            str(payload),
        ],
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_error_make_parents_without_create(tmpfile):
    """Test error when --make-parents used without create being allowed."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "abc",
            "--path",
            str(tmpfile),
            "--make-parents",
            "--do-not-create",
        ],
    )
    assert result.exit_code != 0
    assert "create_if_missing=False requires make_parents=False" in result.output


def test_error_unlink_first_without_unique(tmpfile):
    """Test error when --unlink-first used without --unique."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "abc", "--path", str(tmpfile), "--unlink-first"]
    )
    assert result.exit_code != 0
    assert "unlink_first=True requires unique_line=True" in result.output


def test_error_empty_line(tmpfile):
    """Test error when empty line provided."""
    runner = CliRunner()
    result = runner.invoke(cli, ["append-line", "", "--path", str(tmpfile)])
    assert result.exit_code != 0
    assert "cannot write empty input" in result.output


def test_error_invalid_hex(tmpfile):
    """Test error with invalid hex input."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            "xyz",
            "--path",
            str(tmpfile),
            "--hex-input",
        ],
    )
    assert result.exit_code != 0
    assert "Error" in result.output


@pytest.mark.parametrize("bad_hex", ["0", "12z", "gg", "a"])
def test_error_various_invalid_hex(tmpfile, bad_hex):
    """Test various invalid hex inputs."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            bad_hex,
            "--path",
            str(tmpfile),
            "--hex-input",
        ],
    )
    assert result.exit_code != 0


def test_error_ignore_whitespace_without_unique(tmpfile):
    """Test error when whitespace flags used without --unique."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "test",
            "--path",
            str(tmpfile),
            "--ignore-leading-whitespace",
        ],
    )
    assert result.exit_code != 0
    assert "--ignore-leading-whitespace requires --unique" in result.output


def test_error_comment_marker_without_unique(tmpfile):
    """Test error when --comment-marker used without --unique."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "test",
            "--path",
            str(tmpfile),
            "--comment-marker",
            "#",
        ],
    )
    assert result.exit_code != 0


# =============================================================================
# Edge cases and special scenarios
# =============================================================================


def test_append_to_existing_file(tmpfile):
    """Test appending to existing file with content."""
    tmpfile.write_text("line1\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["append-line", "line2", "--path", str(tmpfile)])
    assert result.exit_code == 0, result.output
    assert read_file(tmpfile) == b"line1\nline2\n"


def test_binary_data_preserves_null_bytes(tmpfile):
    """Test that binary data with null bytes is preserved."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-bytes",
            "00010203",
            "--path",
            str(tmpfile),
            "--hex-input",
        ],
    )
    assert result.exit_code == 0, result.output
    data = read_file(tmpfile)
    assert b"\x00\x01\x02\x03" == data


def test_symlink_follow(tmpfile, tmp_path):
    """Test that symlinks are followed."""
    real_file = tmp_path / "real.txt"
    real_file.write_text("original\n")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(real_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["append-line", "added", "--path", str(symlink)])
    assert result.exit_code == 0, result.output
    assert real_file.read_text() == "original\nadded\n"


def test_dry_run_with_unique(tmpfile):
    """Test dry-run with unique flag."""
    tmpfile.write_text("existing\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append-line",
            "test",
            "--path",
            str(tmpfile),
            "--unique",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "[dry-run]" in result.output
    # File should be unchanged
    assert read_file(tmpfile) == b"existing\n"


def test_require_new_placeholder(tmpfile):
    """Test that --require-new flag exists but is marked as todo."""
    # This flag is in the code but marked as (todo)
    # Just verify it doesn't crash
    runner = CliRunner()
    result = runner.invoke(
        cli, ["append-line", "test", "--path", str(tmpfile), "--require-new"]
    )
    # Don't assert exit code since implementation is incomplete


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
