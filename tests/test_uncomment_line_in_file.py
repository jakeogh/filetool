#!/usr/bin/env python3
"""
Tests for uncomment_line_in_file function.
"""

from pathlib import Path

import pytest

from filetool import uncomment_line_in_file


def test_uncomment_single_line(tmp_path):
    """Test uncommenting a single commented line."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert result == 1, "Should have uncommented 1 line"
    assert config.read_text() == "line1\nline2\nline3\n"


def test_uncomment_multiple_occurrences_with_flag(tmp_path):
    """Test uncommenting all occurrences when multiple=True."""
    config = tmp_path / "config.txt"
    config.write_text("# export FOO=bar\nline2\n# export FOO=bar\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="export FOO=bar",
        comment_marker="#",
        multiple=True,
    )

    assert result == 2, "Should have uncommented 2 lines"
    assert config.read_text() == "export FOO=bar\nline2\nexport FOO=bar\nline3\n"


def test_uncomment_only_first_occurrence_by_default(tmp_path):
    """Test uncommenting only the first occurrence when multiple=False (default)."""
    config = tmp_path / "config.txt"
    config.write_text("# export FOO=bar\nline2\n# export FOO=bar\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="export FOO=bar",
        comment_marker="#",
        multiple=False,
    )

    assert result == 1, "Should have uncommented 1 line"
    assert config.read_text() == "export FOO=bar\nline2\n# export FOO=bar\nline3\n"


def test_uncomment_already_uncommented_line_is_idempotent(tmp_path):
    """Test that uncommenting an already uncommented line returns 0 (no error)."""
    config = tmp_path / "config.txt"
    config.write_text("line1\nline2\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert result == 0, "Should return 0 when line is already uncommented"
    assert config.read_text() == "line1\nline2\nline3\n", "File should be unchanged"


def test_uncomment_line_not_found_raises_error(tmp_path):
    """Test that uncommenting a non-existent line raises ValueError."""
    config = tmp_path / "config.txt"
    config.write_text("line1\nline2\nline3\n")

    with pytest.raises(ValueError, match="Line not found in file"):
        uncomment_line_in_file(
            path=config,
            line="nonexistent",
            comment_marker="#",
        )


def test_uncomment_with_custom_comment_marker(tmp_path):
    """Test uncommenting with a custom comment marker."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n// line2\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="//",
    )

    assert result == 1, "Should have uncommented 1 line"
    assert config.read_text() == "line1\nline2\nline3\n"


def test_uncomment_with_leading_whitespace_ignored(tmp_path):
    """Test uncommenting with ignore_leading_whitespace=True (default)."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n#   line2\nline3\n")

    # The function should match "  line2" (with leading spaces)
    # when we search for "line2" with ignore_leading_whitespace=True
    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        ignore_leading_whitespace=True,
    )

    assert result == 1, "Should have uncommented 1 line"
    # Result preserves original formatting (the two spaces before line2)
    assert config.read_text() == "line1\n  line2\nline3\n"


def test_uncomment_with_trailing_whitespace_ignored(tmp_path):
    """Test uncommenting with ignore_trailing_whitespace=True (default)."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2  \nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        ignore_trailing_whitespace=True,
    )

    assert result == 1, "Should have uncommented 1 line"
    assert config.read_text() == "line1\nline2  \nline3\n"


def test_uncomment_preserves_original_line_formatting(tmp_path):
    """Test that uncommenting preserves the original line's formatting."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n#   line2   \nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert result == 1
    # Original formatting preserved (the spaces after line2)
    assert config.read_text() == "line1\n  line2   \nline3\n"


def test_uncomment_with_crlf_line_ending(tmp_path):
    """Test uncommenting with Windows-style CRLF line endings."""
    config = tmp_path / "config.txt"
    config.write_bytes(b"line1\r\n# line2\r\nline3\r\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        line_ending=b"\r\n",
    )

    assert result == 1
    assert config.read_bytes() == b"line1\r\nline2\r\nline3\r\n"


def test_uncomment_mixed_commented_and_uncommented(tmp_path):
    """Test file with both commented and uncommented versions of the line."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline2\n# line2\nline3\n")

    # With multiple=False, should uncomment only the first commented occurrence
    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        multiple=False,
    )

    assert result == 1
    assert config.read_text() == "line1\nline2\nline2\n# line2\nline3\n"


def test_uncomment_all_mixed_commented_and_uncommented(tmp_path):
    """Test uncommenting all commented lines when uncommented versions also exist."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline2\n# line2\nline3\n")

    # With multiple=True, should uncomment both commented occurrences
    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        multiple=True,
    )

    assert result == 2
    assert config.read_text() == "line1\nline2\nline2\nline2\nline3\n"


def test_uncomment_line_with_spaces_in_comment_marker(tmp_path):
    """Test that comment marker + space is properly handled."""
    config = tmp_path / "config.txt"
    # Note: The function expects "# " (marker + space) before the line
    config.write_text("line1\n# line2\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert result == 1
    assert config.read_text() == "line1\nline2\nline3\n"


def test_uncomment_empty_line_raises_error(tmp_path):
    """Test that uncommenting an empty line raises ValueError."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline3\n")

    with pytest.raises(ValueError, match="line must not be empty"):
        uncomment_line_in_file(
            path=config,
            line="",
            comment_marker="#",
        )


def test_uncomment_line_containing_line_ending_raises_error(tmp_path):
    """Test that uncommenting a line containing the line ending raises ValueError."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline3\n")

    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        uncomment_line_in_file(
            path=config,
            line="line2\nline3",
            comment_marker="#",
        )


def test_uncomment_nonexistent_file_raises_error(tmp_path):
    """Test that uncommenting in a non-existent file raises FileNotFoundError."""
    config = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError):
        uncomment_line_in_file(
            path=config,
            line="line2",
            comment_marker="#",
        )


def test_uncomment_with_different_whitespace_handling(tmp_path):
    """Test uncommenting with different whitespace handling options."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n#   line2  \nline3\n")

    # With both whitespace flags enabled
    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        ignore_leading_whitespace=True,
        ignore_trailing_whitespace=True,
    )

    assert result == 1
    assert config.read_text() == "line1\n  line2  \nline3\n"


def test_uncomment_no_changes_returns_zero(tmp_path):
    """Test that no changes returns 0 (idempotent behavior)."""
    config = tmp_path / "config.txt"
    config.write_text("line1\nline2\nline3\n")

    # First call - line already uncommented
    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert result == 0, "First call should return 0 (already uncommented)"

    # Second call - still uncommented, still returns 0
    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert result == 0, "Second call should return 0 (still uncommented)"
    assert config.read_text() == "line1\nline2\nline3\n"


def test_uncomment_preserves_file_permissions(tmp_path):
    """Test that uncommenting preserves file permissions."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline3\n")
    config.chmod(0o644)

    original_mode = config.stat().st_mode

    uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    assert config.stat().st_mode == original_mode


def test_uncomment_atomic_operation(tmp_path):
    """Test that uncommenting is atomic (no temp files left behind)."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline3\n")

    uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
    )

    # Verify no temporary files remain
    temp_files = list(tmp_path.glob(".filetool.tmp.*"))
    assert len(temp_files) == 0, f"Temporary files not cleaned up: {temp_files}"

    # Verify no hardlinks remain
    link_files = list(tmp_path.glob(".filetool.link.*"))
    assert len(link_files) == 0, f"Hardlink files not cleaned up: {link_files}"


def test_uncomment_multiple_with_no_commented_lines(tmp_path):
    """Test multiple=True when all matching lines are already uncommented."""
    config = tmp_path / "config.txt"
    config.write_text("line1\nline2\nline2\nline3\n")

    result = uncomment_line_in_file(
        path=config,
        line="line2",
        comment_marker="#",
        multiple=True,
    )

    assert result == 0, "Should return 0 when all lines are already uncommented"
    assert config.read_text() == "line1\nline2\nline2\nline3\n"


def test_uncomment_type_errors(tmp_path):
    """Test that incorrect parameter types raise TypeError."""
    config = tmp_path / "config.txt"
    config.write_text("line1\n# line2\nline3\n")

    # Wrong type for path
    with pytest.raises(TypeError, match="path must be Path"):
        uncomment_line_in_file(
            path="not_a_path",
            line="line2",
            comment_marker="#",
        )

    # Wrong type for line
    with pytest.raises(TypeError, match="line must be str"):
        uncomment_line_in_file(
            path=config,
            line=123,
            comment_marker="#",
        )

    # Wrong type for comment_marker
    with pytest.raises(TypeError, match="comment_marker must be str"):
        uncomment_line_in_file(
            path=config,
            line="line2",
            comment_marker=123,
        )

    # Wrong type for line_ending
    with pytest.raises(TypeError, match="line_ending must be bytes"):
        uncomment_line_in_file(
            path=config,
            line="line2",
            comment_marker="#",
            line_ending="\n",
        )

    # Wrong type for multiple
    with pytest.raises(TypeError, match="multiple must be bool"):
        uncomment_line_in_file(
            path=config,
            line="line2",
            comment_marker="#",
            multiple="yes",
        )
