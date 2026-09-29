#!/usr/bin/env python3
"""
Tests for edge cases and error paths in filetool core functions.
"""

import pytest

from filetool import comment_out_line_in_file
from filetool import uncomment_line_in_file


def test_comment_out_empty_line_raises_error(tmp_path):
    """Test that commenting out empty line raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(ValueError, match="line must not be empty"):
        comment_out_line_in_file(
            path=test_file,
            line="",
        )


def test_comment_out_empty_comment_marker_raises_error(tmp_path):
    """Test that empty comment marker raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(ValueError, match="comment_marker must not be empty"):
        comment_out_line_in_file(
            path=test_file,
            line="line1",
            comment_marker="",
        )


def test_comment_out_empty_line_ending_raises_error(tmp_path):
    """Test that empty line_ending raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(ValueError, match="line_ending must not be empty"):
        comment_out_line_in_file(
            path=test_file,
            line="line1",
            line_ending=b"",
        )


def test_comment_out_line_with_line_ending_raises_error(tmp_path):
    """Test that line containing line_ending raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        comment_out_line_in_file(
            path=test_file,
            line="line1\nline2",
        )


def test_comment_out_wrong_path_type_raises_error(tmp_path):
    """Test that wrong path type raises TypeError."""
    with pytest.raises(TypeError, match="path must be Path"):
        comment_out_line_in_file(
            path="not_a_path",
            line="line1",
        )


def test_comment_out_wrong_line_type_raises_error(tmp_path):
    """Test that wrong line type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(TypeError, match="line must be str"):
        comment_out_line_in_file(
            path=test_file,
            line=123,
        )


def test_comment_out_wrong_comment_marker_type_raises_error(tmp_path):
    """Test that wrong comment_marker type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(TypeError, match="comment_marker must be str"):
        comment_out_line_in_file(
            path=test_file,
            line="line1",
            comment_marker=123,
        )


def test_comment_out_wrong_line_ending_type_raises_error(tmp_path):
    """Test that wrong line_ending type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(TypeError, match="line_ending must be bytes"):
        comment_out_line_in_file(
            path=test_file,
            line="line1",
            line_ending="\n",
        )


def test_uncomment_empty_line_raises_error(tmp_path):
    """Test that uncommenting empty line raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(ValueError, match="line must not be empty"):
        uncomment_line_in_file(
            path=test_file,
            line="",
        )


def test_uncomment_empty_comment_marker_raises_error(tmp_path):
    """Test that empty comment marker raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(ValueError, match="comment_marker must not be empty"):
        uncomment_line_in_file(
            path=test_file,
            line="line1",
            comment_marker="",
        )


def test_uncomment_empty_line_ending_raises_error(tmp_path):
    """Test that empty line_ending raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(ValueError, match="line_ending must not be empty"):
        uncomment_line_in_file(
            path=test_file,
            line="line1",
            line_ending=b"",
        )


def test_uncomment_line_with_line_ending_raises_error(tmp_path):
    """Test that line containing line_ending raises ValueError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        uncomment_line_in_file(
            path=test_file,
            line="line1\nline2",
        )


def test_uncomment_wrong_path_type_raises_error(tmp_path):
    """Test that wrong path type raises TypeError."""
    with pytest.raises(TypeError, match="path must be Path"):
        uncomment_line_in_file(
            path="not_a_path",
            line="line1",
        )


def test_uncomment_wrong_line_type_raises_error(tmp_path):
    """Test that wrong line type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(TypeError, match="line must be str"):
        uncomment_line_in_file(
            path=test_file,
            line=123,
        )


def test_uncomment_wrong_comment_marker_type_raises_error(tmp_path):
    """Test that wrong comment_marker type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(TypeError, match="comment_marker must be str"):
        uncomment_line_in_file(
            path=test_file,
            line="line1",
            comment_marker=123,
        )


def test_uncomment_wrong_line_ending_type_raises_error(tmp_path):
    """Test that wrong line_ending type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(TypeError, match="line_ending must be bytes"):
        uncomment_line_in_file(
            path=test_file,
            line="line1",
            line_ending="\n",
        )


def test_uncomment_wrong_multiple_type_raises_error(tmp_path):
    """Test that wrong multiple type raises TypeError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(TypeError, match="multiple must be bool"):
        uncomment_line_in_file(
            path=test_file,
            line="line1",
            multiple="yes",
        )


def test_comment_out_nonexistent_file_raises_error(tmp_path):
    """Test that commenting in non-existent file raises FileNotFoundError."""
    test_file = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError):
        comment_out_line_in_file(
            path=test_file,
            line="line1",
        )


def test_uncomment_nonexistent_file_raises_error(tmp_path):
    """Test that uncommenting in non-existent file raises FileNotFoundError."""
    test_file = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError):
        uncomment_line_in_file(
            path=test_file,
            line="line1",
        )


def test_comment_out_unterminated_final_line(tmp_path):
    config = tmp_path / "config.txt"
    config.write_bytes(b"a\nb")

    assert comment_out_line_in_file(path=config, line="b") == 1
    assert config.read_bytes() == b"a\n# b"


def test_comment_out_symlinked_config(tmp_path):
    real = tmp_path / "real.conf"
    real.write_bytes(b"export FOO=bar\n")
    link = tmp_path / "link.conf"
    link.symlink_to(real)

    assert comment_out_line_in_file(path=link, line="export FOO=bar") == 1
    assert link.is_symlink()
    assert real.read_bytes() == b"# export FOO=bar\n"
