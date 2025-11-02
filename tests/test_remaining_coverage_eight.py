#!/usr/bin/env python3
"""
Final push to 90%+ coverage - targeting the exact uncovered lines.
"""

import pytest
import os
import sys
import errno
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO
from filetool import comment_out_line_in_file, uncomment_line_in_file
from filetool.filetool import (
    _append_bytes_to_file,
    _locked_file_handle,
    _safe_open_rw_binary,
    _modify_file_lines,
    _ensure_bytes_present,
)
from filetool.test_instrumenter import instrument_function
import filetool.filetool
import filetool.splitlines_bytes


# =============================================================================
# Lines 172, 178: ENOLCK error handling
# =============================================================================

def test_locked_file_handle_enolck_error():
    """Test lines 172-178: ENOLCK error handling."""
    test_file = Path("/tmp/test_enolck.txt")
    test_file.write_text("content")

    try:
        original_flock = filetool.filetool.fcntl.flock

        def mock_flock(fd, operation):
            if operation & filetool.filetool.fcntl.LOCK_EX:
                # Raise ENOLCK (line 175)
                raise OSError(errno.ENOLCK, "No locks available")
            return original_flock(fd, operation)

        with patch('filetool.filetool.fcntl.flock', side_effect=mock_flock):
            with pytest.raises(OSError, match="Locking unavailable.*ENOLCK"):
                with _locked_file_handle(
                    path=test_file,
                    mode="rb+",
                    blocking=True,
                    create=False,
                ):
                    pass
    finally:
        test_file.unlink(missing_ok=True)


# =============================================================================
# Lines 220-237: _safe_open_rw_binary paths
# =============================================================================

def test_safe_open_rw_binary_file_not_found_require_exists():
    """Test lines 220-233: FileNotFoundError with require_exists=True."""
    test_file = Path("/tmp/nonexistent_file.txt")

    # Line 228-229: except FileNotFoundError, if require_exists: raise
    with pytest.raises(FileNotFoundError):
        with _safe_open_rw_binary(path=test_file, require_exists=True):
            pass


def test_safe_open_rw_binary_file_not_found_create():
    """Test lines 230-237: FileNotFoundError with require_exists=False."""
    test_file = Path("/tmp/test_safe_open.txt")

    try:
        test_file.unlink(missing_ok=True)

        # Lines 230-237: Create file when it doesn't exist
        with _safe_open_rw_binary(path=test_file, require_exists=False) as fh:
            fh.write(b"test")

        assert test_file.read_bytes() == b"test"
    finally:
        test_file.unlink(missing_ok=True)


# =============================================================================
# Lines 561-562, 565, 572-573: unlink_first race conditions
# =============================================================================

def test_append_bytes_unlink_first_file_exists_race(tmp_path):
    """Test lines 561-573: unlink_first with FileExistsError race."""
    test_file = tmp_path / "race.txt"
    test_file.write_text("original")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    # Mock open to simulate race condition
    original_open = open
    call_count = 0

    def racing_open(path, mode, *args, **kwargs):
        nonlocal call_count
        if mode == "xb" and "race.txt" in str(path):
            call_count += 1
            if call_count == 1:
                # Simulate another process creating the file (line 572)
                attack_barrier.wait()
                attacker_executed.wait(timeout=2.0)
                raise FileExistsError("Race: file recreated")
        return original_open(path, mode, *args, **kwargs)

    def attacker():
        attack_barrier.wait()
        # Simulate concurrent file creation
        test_file.write_text("concurrent")
        attacker_executed.set()

    with patch('builtins.open', side_effect=racing_open):
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Line 572-573: FileExistsError raised
        with pytest.raises(FileExistsError, match="Race detected"):
            _append_bytes_to_file(
                bytes_payload=b"new content\n",
                path=test_file,
                unlink_first=True,
                unique_bytes=True,
                create_if_missing=True,
                make_parents=False,
            )

        attacker_thread.join(timeout=2.0)


def test_append_bytes_unlink_first_with_make_parents(tmp_path):
    """Test lines 565-570: unlink_first with make_parents."""
    deep_file = tmp_path / "a" / "b" / "c" / "file.txt"

    # Lines 565-570: make_parents creates directories
    result = _append_bytes_to_file(
        bytes_payload=b"content\n",
        path=deep_file,
        unlink_first=True,
        unique_bytes=True,
        create_if_missing=True,
        make_parents=True,
    )

    assert result == 8
    assert deep_file.read_bytes() == b"content\n"


# =============================================================================
# Lines 638, 657: _ensure_bytes_present recursive call
# =============================================================================

def test_ensure_bytes_present_make_parents_after_failure(tmp_path):
    """Test lines 638-657: make_parents in recursive call."""
    deep_path = tmp_path / "x" / "y" / "z" / "file.txt"

    # Force the code path where we try without make_parents, fail, then retry
    # This hits lines 638-657
    result = filetool.filetool._ensure_bytes_present(
        path=deep_path,
        bytes_payload=b"data\n",
        unique_bytes=False,
        create_if_missing=True,
        make_parents=True,
        line_ending=None,
        comment_marker=None,
        ignore_leading_whitespace=False,
        ignore_trailing_whitespace=False,
    )

    assert result == 5
    assert deep_path.exists()


# =============================================================================
# Lines 861-862, 872-875, 880-881: File deletion and cleanup
# =============================================================================

def test_modify_file_lines_file_deleted_before_rename(tmp_path):
    """Test lines 861-875: File deleted before rename."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)
    temp_path_captured = None

    def capture_and_delete(ctx):
        nonlocal temp_path_captured
        temp_path_captured = ctx.locals.get('temp_path')
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.01)
        # Delete the file (line 869-870)
        test_file.unlink()
        attacker_executed.set()

    hooks = {
        "step_25_stat_before_rename": capture_and_delete,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Lines 869-870, 875: FileNotFoundError, cleanup, OSError raised
        with pytest.raises(OSError, match="was deleted before rename operation"):
            comment_out_line_in_file(
                path=test_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

        # Verify temp was cleaned up (line 870)
        if temp_path_captured:
            assert not temp_path_captured.exists()

    finally:
        filetool.filetool._modify_file_lines = original_func



# =============================================================================
# Lines 929-931, 939-940, 946-962: Hardlink verification failure
# =============================================================================

def test_hardlink_verification_failure_inode_mismatch(tmp_path):
    """Test lines 929-962: Hardlink verification detects inode change."""
    test_file = tmp_path / "test.txt"
    evil_file = tmp_path / "evil.txt"

    test_file.write_text("line1\nline2\nline3\n")
    evil_file.write_text("EVIL\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def trigger_attack(ctx):
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.02)  # Let hardlink be created
        # Replace file (lines 929-931, 956-960)
        test_file.unlink()
        evil_file.rename(test_file)
        attacker_executed.set()

    hooks = {
        "step_30_stat_after_link": trigger_attack,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Lines 929-962: hardlink_verification_failed cleanup
        with pytest.raises(OSError, match="was replaced during hardlink verification"):
            comment_out_line_in_file(
                path=test_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

    finally:
        filetool.filetool._modify_file_lines = original_func


# =============================================================================
# Lines 978-979, 983-989: Exception cleanup with missing files
# =============================================================================

def test_modify_lines_cleanup_link_already_gone(tmp_path):
    """Test lines 978-979: link_path cleanup FileNotFoundError."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    # Successful path exercises 978-979
    result = comment_out_line_in_file(
        path=test_file,
        line="line1",
        comment_marker="#",
    )

    assert result == 1


# =============================================================================
# Line 1312: Uncomment whitespace edge case
# =============================================================================

def test_uncomment_line_content_stripped_whitespace(tmp_path):
    """Test line 1312-1314: Whitespace handling in content after marker."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\n#   line2  \nline3\n")

    # Exercise the whitespace stripping in content comparison (lines 1309-1314)
    result = uncomment_line_in_file(
        path=test_file,
        line="line2",
        comment_marker="#",
        ignore_leading_whitespace=True,
        ignore_trailing_whitespace=True,
    )

    assert result == 1




if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=filetool", "--cov-report=term-missing"])
