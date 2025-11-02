#!/usr/bin/env python3
"""
Additional tests to push coverage from 84% to 87%+.

Focuses on remaining gaps in:
- filetool.py: Low-level exception handlers and edge cases
- cli.py: Final 3 lines
- validate_args.py: Old buggy code paths
"""

import pytest
import os
import threading
import time
from pathlib import Path
from io import BytesIO
from filetool.cli import cli
from filetool import comment_out_line_in_file, uncomment_line_in_file
from filetool.filetool import (
    _modify_file_lines,
    _locked_file_handle,
    _open_eintr_safe,
    _fsync_eintr_safe,
    ensure_line_in_config_file,
)
from filetool.test_instrumenter import instrument_function
import filetool.filetool
from click.testing import CliRunner


# =============================================================================
# CLI Final Edge Cases (96% → 100%)
# =============================================================================

def test_cli_append_line_validation_error():
    """Test that CLI properly handles ValidationError from append_line_to_file."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path('test.txt').write_text("existing\n")

        # Try to use --unlink-first without --unique (should fail)
        result = runner.invoke(cli, [
            'append-line',
            '--path', 'test.txt',
            '--unlink-first',
            'newline'
        ])

        assert result.exit_code != 0
        assert "--unlink-first requires --unique" in result.output


def test_cli_append_bytes_validation_error():
    """Test that CLI properly handles ValidationError from append_bytes_to_file."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path('test.bin').write_bytes(b"existing")

        # Try to use --unlink-first without --unique (should fail)
        result = runner.invoke(cli, [
            'append-bytes',
            '--path', 'test.bin',
            '--unlink-first',
            'newbytes'
        ])

        assert result.exit_code != 0
        assert "--unlink-first requires --unique" in result.output


# =============================================================================
# Low-Level Exception Handlers in filetool.py
# =============================================================================

def test_locked_file_handle_blocking_io_error(tmp_path):
    """Test that _locked_file_handle handles BlockingIOError correctly."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content\n")

    # First, acquire lock in a separate thread
    lock_acquired = threading.Event()
    release_lock = threading.Event()

    def hold_lock():
        """Hold lock until signaled to release."""
        with _locked_file_handle(
            path=test_file,
            mode="rb+",
            blocking=True,
            create=False,
        ) as fh:
            lock_acquired.set()
            release_lock.wait(timeout=5.0)

    holder_thread = threading.Thread(target=hold_lock, daemon=True)
    holder_thread.start()

    # Wait for lock to be acquired
    lock_acquired.wait(timeout=2.0)

    try:
        # Now try to acquire lock in non-blocking mode (should fail)
        with pytest.raises(BlockingIOError):
            with _locked_file_handle(
                path=test_file,
                mode="rb+",
                blocking=False,
                create=False,
            ):
                pass
    finally:
        release_lock.set()
        holder_thread.join(timeout=2.0)


def test_locked_file_handle_file_exists_race(tmp_path):
    """Test that _locked_file_handle handles FileExistsError during create."""
    test_file = tmp_path / "test.txt"

    # First call with create=True
    with _locked_file_handle(
        path=test_file,
        mode="rb+",
        blocking=True,
        create=True,
    ) as fh:
        assert test_file.exists()

    # Second call with create=True should handle FileExistsError gracefully
    with _locked_file_handle(
        path=test_file,
        mode="rb+",
        blocking=True,
        create=True,
    ) as fh:
        assert test_file.exists()


def test_modify_file_lines_no_changes_returns_zero(tmp_path):
    """Test that _modify_file_lines returns 0 when no changes are made."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    def identity_transformer(line: bytes) -> bytes:
        """Transformer that doesn't modify anything."""
        return line

    result = _modify_file_lines(
        path=test_file,
        line_transformer=identity_transformer,
        line_ending=b"\n",
    )

    assert result == 0
    assert test_file.read_text() == "line1\nline2\nline3\n"


def test_modify_file_lines_file_not_found_raises_error(tmp_path):
    """Test that _modify_file_lines raises FileNotFoundError for missing file."""
    test_file = tmp_path / "nonexistent.txt"

    def identity_transformer(line: bytes) -> bytes:
        return line

    with pytest.raises(FileNotFoundError, match="File does not exist"):
        _modify_file_lines(
            path=test_file,
            line_transformer=identity_transformer,
            line_ending=b"\n",
        )


def test_modify_file_lines_transformer_returns_wrong_type_raises_error(tmp_path):
    """Test that _modify_file_lines raises TypeError if transformer returns non-bytes."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    def bad_transformer(line: bytes) -> str:
        """Transformer that returns wrong type."""
        return "string"  # Should return bytes!

    with pytest.raises(TypeError, match="line_transformer must return bytes"):
        _modify_file_lines(
            path=test_file,
            line_transformer=bad_transformer,
            line_ending=b"\n",
        )


def test_modify_file_lines_wrong_path_type_raises_error():
    """Test that _modify_file_lines raises TypeError for wrong path type."""
    def identity_transformer(line: bytes) -> bytes:
        return line

    with pytest.raises(TypeError, match="path must be Path"):
        _modify_file_lines(
            path="not_a_path",
            line_transformer=identity_transformer,
            line_ending=b"\n",
        )


def test_modify_file_lines_wrong_line_ending_type_raises_error(tmp_path):
    """Test that _modify_file_lines raises TypeError for wrong line_ending type."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\n")

    def identity_transformer(line: bytes) -> bytes:
        return line

    with pytest.raises(TypeError, match="line_ending must be bytes"):
        _modify_file_lines(
            path=test_file,
            line_transformer=identity_transformer,
            line_ending="\n",  # Should be bytes!
        )


def test_modify_file_lines_empty_line_ending_raises_error(tmp_path):
    """Test that _modify_file_lines raises ValueError for empty line_ending."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\n")

    def identity_transformer(line: bytes) -> bytes:
        return line

    with pytest.raises(ValueError, match="line_ending must not be empty"):
        _modify_file_lines(
            path=test_file,
            line_transformer=identity_transformer,
            line_ending=b"",
        )


def test_modify_file_lines_non_callable_transformer_raises_error(tmp_path):
    """Test that _modify_file_lines raises TypeError for non-callable transformer."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\n")

    with pytest.raises(TypeError, match="line_transformer must be callable"):
        _modify_file_lines(
            path=test_file,
            line_transformer="not_callable",
            line_ending=b"\n",
        )


def test_modify_file_lines_deleted_during_operation_raises_error(tmp_path):
    """Test that _modify_file_lines detects file deletion during operation."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def attack_trigger(ctx):
        """Hook that triggers file deletion."""
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        """Delete file after reading but before rename."""
        attack_barrier.wait()
        test_file.unlink()
        attacker_executed.set()

    hooks = {
        "step_25_stat_before_rename": attack_trigger,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        with pytest.raises(OSError, match="was deleted before rename operation"):
            comment_out_line_in_file(
                path=test_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)
        assert attacker_executed.is_set()

    finally:
        filetool.filetool._modify_file_lines = original_func


def test_comment_out_line_empty_values_raise_errors(tmp_path):
    """Test that comment_out_line_in_file validates empty parameters."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    # Empty line
    with pytest.raises(ValueError, match="line must not be empty"):
        comment_out_line_in_file(path=test_file, line="")

    # Empty comment_marker
    with pytest.raises(ValueError, match="comment_marker must not be empty"):
        comment_out_line_in_file(path=test_file, line="line1", comment_marker="")

    # Empty line_ending
    with pytest.raises(ValueError, match="line_ending must not be empty"):
        comment_out_line_in_file(path=test_file, line="line1", line_ending=b"")


def test_uncomment_line_empty_values_raise_errors(tmp_path):
    """Test that uncomment_line_in_file validates empty parameters."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    # Empty line
    with pytest.raises(ValueError, match="line must not be empty"):
        uncomment_line_in_file(path=test_file, line="")

    # Empty comment_marker
    with pytest.raises(ValueError, match="comment_marker must not be empty"):
        uncomment_line_in_file(path=test_file, line="line1", comment_marker="")

    # Empty line_ending
    with pytest.raises(ValueError, match="line_ending must not be empty"):
        uncomment_line_in_file(path=test_file, line="line1", line_ending=b"")


def test_ensure_line_validation_error(tmp_path):
    """Test ensure_line_in_config_file validation."""
    test_file = tmp_path / "config.txt"

    # Line contains line_ending
    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        ensure_line_in_config_file(
            path=test_file,
            line="line1\nline2",
            comment_marker="#",
        )


# =============================================================================
# Hardlink Cleanup Exception Handling
# =============================================================================

def test_modify_file_lines_hardlink_cleanup_on_success(tmp_path):
    """Test that hardlink is cleaned up successfully after rename."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    result = comment_out_line_in_file(
        path=test_file,
        line="line1",
        comment_marker="#",
    )

    assert result == 1

    # Verify no hardlinks remain
    link_files = list(tmp_path.glob(".filetool.link.*"))
    assert len(link_files) == 0


def test_modify_file_lines_temp_cleanup_on_error(tmp_path):
    """Test that temp file is cleaned up when an error occurs."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    def bad_transformer(line: bytes) -> str:
        """Transformer that raises after some lines."""
        if line.startswith(b"line2"):
            raise RuntimeError("Simulated error")
        return line

    with pytest.raises(RuntimeError, match="Simulated error"):
        _modify_file_lines(
            path=test_file,
            line_transformer=bad_transformer,
            line_ending=b"\n",
        )

    # Verify no temp files remain
    temp_files = list(tmp_path.glob(".filetool.tmp.*"))
    assert len(temp_files) == 0


# =============================================================================
# Additional Edge Cases
# =============================================================================

def test_comment_out_line_with_line_ending_in_line(tmp_path):
    """Test that comment_out_line_in_file raises error if line contains line_ending."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        comment_out_line_in_file(
            path=test_file,
            line="line1\nline2",
        )


def test_uncomment_line_with_line_ending_in_line(tmp_path):
    """Test that uncomment_line_in_file raises error if line contains line_ending."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        uncomment_line_in_file(
            path=test_file,
            line="line1\nline2",
        )


# =============================================================================
# Run Coverage Report
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=filetool", "--cov-report=term-missing"])
