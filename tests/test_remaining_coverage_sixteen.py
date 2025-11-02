#!/usr/bin/env python3
"""
PUSH TO 96%+ COVERAGE - FIXED VERSION

Targeting all 37 remaining lines with proper timing
"""

import pytest
import os
import errno
import threading
import time
from pathlib import Path
from unittest.mock import patch
from filetool import comment_out_line_in_file, uncomment_line_in_file
from filetool.filetool import (
    _locked_file_handle,
    _safe_open_rw_binary,
    _modify_file_lines,
    _ensure_bytes_present,
)
from filetool.test_instrumenter import instrument_function
import filetool.filetool


# =============================================================================
# Lines 172, 178: ENOLCK error
# =============================================================================

def test_enolck_error_with_retry():
    """Test lines 172-178: EINTR retry then ENOLCK error."""
    test_file = Path("/tmp/test_enolck.txt")
    test_file.write_text("content")

    try:
        original_flock = filetool.filetool.fcntl.flock
        call_count = 0

        def mock_flock(fd, operation):
            nonlocal call_count
            if operation & filetool.filetool.fcntl.LOCK_EX:
                call_count += 1
                if call_count == 1:
                    # Line 172: continue on EINTR
                    raise OSError(errno.EINTR, "Interrupted")
                elif call_count == 2:
                    # Lines 174-177: ENOLCK
                    raise OSError(errno.ENOLCK, "No locks")
            return original_flock(fd, operation)

        with patch('filetool.filetool.fcntl.flock', side_effect=mock_flock):
            with pytest.raises(OSError, match="Locking unavailable"):
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
# Line 227: yield fh
# =============================================================================

def test_safe_open_existing():
    """Test line 227: yield fh when file exists."""
    test_file = Path("/tmp/test227.txt")
    test_file.write_text("content")

    try:
        with _safe_open_rw_binary(path=test_file, require_exists=False) as fh:
            assert fh.read() == b"content"
    finally:
        test_file.unlink(missing_ok=True)


# =============================================================================
# Lines 638, 657: Recursive call
# =============================================================================

def test_ensure_bytes_recursive(tmp_path):
    """Test lines 638, 657: mkdir then recursive call."""
    deep = tmp_path / "a" / "b" / "c" / "file.txt"

    result = _ensure_bytes_present(
        path=deep,
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
    assert deep.exists()


# =============================================================================
# Line 772: File replaced between stat and open
# =============================================================================

def test_file_replaced_stat_open(tmp_path):
    """Test line 772: File replaced between stat and open."""
    test_file = tmp_path / "test.txt"
    evil_file = tmp_path / "evil.txt"

    test_file.write_text("line1\nline2\n")
    evil_file.write_text("EVIL\n")

    attack_barrier = threading.Barrier(2)
    attacker_done = threading.Event()

    def trigger(ctx):
        attack_barrier.wait()
        attacker_done.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.001)
        test_file.unlink()
        evil_file.rename(test_file)
        attacker_done.set()

    instrumented = instrument_function(_modify_file_lines, {"step_6_call__locked_file_handle": trigger})
    original = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        thread = threading.Thread(target=attacker, daemon=True)
        thread.start()

        with pytest.raises(OSError, match="was replaced between stat and open"):
            comment_out_line_in_file(path=test_file, line="line1", comment_marker="#")

        thread.join(timeout=2.0)
    finally:
        filetool.filetool._modify_file_lines = original


# =============================================================================
# Lines 792-795: File deleted during read
# =============================================================================

def test_file_deleted_during_read(tmp_path):
    """Test lines 792-795: FileNotFoundError during read."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    attack_barrier = threading.Barrier(2)
    attacker_done = threading.Event()

    def trigger(ctx):
        attack_barrier.wait()
        attacker_done.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.001)
        test_file.unlink()
        attacker_done.set()

    instrumented = instrument_function(_modify_file_lines, {"step_13_stat_after_read": trigger})
    original = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        thread = threading.Thread(target=attacker, daemon=True)
        thread.start()

        with pytest.raises(OSError, match="was deleted during read"):
            comment_out_line_in_file(path=test_file, line="line1", comment_marker="#")

        thread.join(timeout=2.0)
    finally:
        filetool.filetool._modify_file_lines = original


# =============================================================================
# Lines 796-801: File replaced during read
# =============================================================================

def test_file_replaced_after_read(tmp_path):
    """Test lines 796-801: File replaced after reading."""
    test_file = tmp_path / "test.txt"
    evil_file = tmp_path / "evil.txt"

    test_file.write_text("line1\nline2\n")
    evil_file.write_text("EVIL\n")

    attack_barrier = threading.Barrier(2)
    attacker_done = threading.Event()

    def trigger(ctx):
        attack_barrier.wait()
        attacker_done.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        # Wait for the comparison to happen
        time.sleep(0.005)
        test_file.unlink()
        evil_file.rename(test_file)
        attacker_done.set()

    # Hook BEFORE the comparison
    instrumented = instrument_function(_modify_file_lines, {"step_13_stat_after_read": trigger})
    original = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        thread = threading.Thread(target=attacker, daemon=True)
        thread.start()

        # Should hit line 796-801 check
        with pytest.raises(OSError, match="was replaced during read|was replaced before rename"):
            comment_out_line_in_file(path=test_file, line="line1", comment_marker="#")

        thread.join(timeout=2.0)
    finally:
        filetool.filetool._modify_file_lines = original


# =============================================================================
# Lines 872-881: File operations before rename
# =============================================================================

def test_file_deleted_before_rename(tmp_path):
    """Test lines 872-875: File deleted before rename."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    attack_barrier = threading.Barrier(2)
    attacker_done = threading.Event()

    def trigger(ctx):
        attack_barrier.wait()
        attacker_done.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.001)
        test_file.unlink()
        attacker_done.set()

    instrumented = instrument_function(_modify_file_lines, {"step_25_stat_before_rename": trigger})
    original = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        thread = threading.Thread(target=attacker, daemon=True)
        thread.start()

        with pytest.raises(OSError, match="was deleted before rename"):
            comment_out_line_in_file(path=test_file, line="line1", comment_marker="#")

        thread.join(timeout=2.0)
    finally:
        filetool.filetool._modify_file_lines = original


# =============================================================================
# Lines 929-931, 946-962: Hardlink verification
# =============================================================================

def test_hardlink_verification_cleanup(tmp_path):
    """Test lines 929-962: Hardlink verification and cleanup."""
    test_file = tmp_path / "test.txt"
    evil_file = tmp_path / "evil.txt"

    test_file.write_text("line1\nline2\n")
    evil_file.write_text("EVIL\n")

    attack_barrier = threading.Barrier(2)
    attacker_done = threading.Event()

    def trigger(ctx):
        attack_barrier.wait()
        attacker_done.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.02)
        test_file.unlink()
        evil_file.rename(test_file)
        attacker_done.set()

    instrumented = instrument_function(_modify_file_lines, {"step_30_stat_after_link": trigger})
    original = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        thread = threading.Thread(target=attacker, daemon=True)
        thread.start()

        with pytest.raises(OSError, match="was replaced during hardlink"):
            comment_out_line_in_file(path=test_file, line="line1", comment_marker="#")

        thread.join(timeout=2.0)
    finally:
        filetool.filetool._modify_file_lines = original


# =============================================================================
# Lines 983-989: Exception cleanup
# =============================================================================

def test_exception_cleanup_temp(tmp_path):
    """Test lines 983-989: Temp cleanup on exception."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    original_unlink = Path.unlink

    def bad_transformer(line: bytes) -> bytes:
        if b"line2" in line:
            raise RuntimeError("Error")
        return line

    def mock_unlink(self, *args, **kwargs):
        if ".filetool.tmp." in str(self):
            raise FileNotFoundError("Already gone")
        return original_unlink(self, *args, **kwargs)

    with patch.object(Path, 'unlink', mock_unlink):
        with pytest.raises(RuntimeError):
            _modify_file_lines(
                path=test_file,
                line_transformer=bad_transformer,
                line_ending=b"\n",
            )


# =============================================================================
# Line 1312: Uncomment edge case
# =============================================================================

def test_uncomment_whitespace_content(tmp_path):
    """Test line 1312: Whitespace content handling."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("#   \n# line2\n")

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
