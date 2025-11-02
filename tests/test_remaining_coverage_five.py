#!/usr/bin/env python3
"""
Targeted tests for ACTUALLY uncovered lines.

Strategy: Execute real code, not mocks, to hit actual branches.
"""

import pytest
import os
import errno
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from filetool import comment_out_line_in_file, uncomment_line_in_file
from filetool.filetool import (
    _modify_file_lines,
    _ensure_bytes_present,
    ensure_line_in_config_file,
)
from filetool.test_instrumenter import instrument_function
import filetool.filetool


# =============================================================================
# Lines 929-931, 937-940: Hardlink inode mismatch branch
# =============================================================================

def test_hardlink_inode_mismatch_detected(tmp_path):
    """Test detection of inode change after hardlink (lines 937-940)."""
    config_file = tmp_path / "config.txt"
    evil_file = tmp_path / "evil.txt"

    config_file.write_text("line1\nline2\nline3\n")
    evil_file.write_text("EVIL\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)
    original_inode = None

    def capture_and_attack(ctx):
        nonlocal original_inode
        original_inode = ctx.locals.get('inode_before')
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        """Replace file with different inode after hardlink creation."""
        attack_barrier.wait()
        time.sleep(0.01)  # Let hardlink be created
        # Unlink original and replace with new file (new inode)
        config_file.unlink()
        evil_file.rename(config_file)
        attacker_executed.set()

    hooks = {
        "step_28_create_hardlink": capture_and_attack,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Should detect inode mismatch and raise OSError (line 937-940)
        with pytest.raises(OSError, match="was replaced during hardlink verification"):
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)
        assert attacker_executed.is_set()

    finally:
        filetool.filetool._modify_file_lines = original_func


def test_hardlink_link_count_mismatch_detected(tmp_path):
    """Test detection of link count mismatch (lines 929-931, 946-951)."""
    # This is covered by test_attack_1_hardlink_exhaustion
    # But let's be explicit about which lines we're testing
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\nline2\nline3\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def attack_trigger(ctx):
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        """Create extra hardlinks to cause link count mismatch."""
        attack_barrier.wait()
        time.sleep(0.01)
        # Create multiple hardlinks
        for i in range(5):
            try:
                os.link(config_file, tmp_path / f"extra_link_{i}")
            except:
                pass
        attacker_executed.set()

    hooks = {
        "step_29_calculate_expected_link_count": attack_trigger,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Should detect link count mismatch (lines 946-951)
        with pytest.raises(OSError, match="link count mismatch"):
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

    finally:
        filetool.filetool._modify_file_lines = original_func


# =============================================================================
# Lines 946-962: Hardlink exception cleanup paths
# =============================================================================

def test_hardlink_verification_cleanup_on_inode_failure(tmp_path):
    """Test cleanup of hardlink and temp on inode verification failure (lines 953-962)."""
    config_file = tmp_path / "config.txt"
    evil_file = tmp_path / "evil.txt"

    config_file.write_text("line1\nline2\nline3\n")
    evil_file.write_text("EVIL\n")

    temp_path_captured = None
    link_path_captured = None
    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def capture_paths_and_attack(ctx):
        nonlocal temp_path_captured, link_path_captured
        temp_path_captured = ctx.locals.get('temp_path')
        link_path_captured = ctx.locals.get('link_path')
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        attack_barrier.wait()
        time.sleep(0.01)
        config_file.unlink()
        evil_file.rename(config_file)
        attacker_executed.set()

    hooks = {
        "step_28_create_hardlink": capture_paths_and_attack,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        with pytest.raises(OSError):
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

        # Verify cleanup happened (lines 953-962)
        if temp_path_captured:
            assert not temp_path_captured.exists(), "Temp file should be cleaned up"
        if link_path_captured:
            assert not link_path_captured.exists(), "Link file should be cleaned up"

    finally:
        filetool.filetool._modify_file_lines = original_func


# =============================================================================
# Lines 978-979, 983-989: Temp file cleanup exception handling
# =============================================================================

def test_temp_file_cleanup_on_exception(tmp_path):
    """Test that temp file is cleaned up when exception occurs (lines 978-989)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    temp_file_created = []

    def bad_transformer(line: bytes) -> bytes:
        # Raise exception after temp file is created
        if line.startswith(b"line2"):
            # At this point temp file should exist
            # Find it
            for f in tmp_path.glob(".filetool.tmp.*"):
                temp_file_created.append(f)
            raise RuntimeError("Intentional error for testing")
        return line

    # This should trigger exception cleanup path (lines 978-989)
    with pytest.raises(RuntimeError, match="Intentional error"):
        _modify_file_lines(
            path=test_file,
            line_transformer=bad_transformer,
            line_ending=b"\n",
        )

    # Verify temp file was cleaned up
    temp_files = list(tmp_path.glob(".filetool.tmp.*"))
    assert len(temp_files) == 0, "Temp files should be cleaned up after exception"


# =============================================================================
# Actually test the TYPE ERRORS by creating real Path objects
# =============================================================================

def test_comment_out_line_actual_type_errors(tmp_path):
    """Test actual type errors with real files (lines 1096, 1106)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")

    # These actually execute the validation code
    with pytest.raises(TypeError):
        comment_out_line_in_file(path="string_not_path", line="test")

    with pytest.raises(TypeError):
        comment_out_line_in_file(path=test_file, line=123)

    with pytest.raises(TypeError):
        comment_out_line_in_file(path=test_file, line="test", comment_marker=123)

    with pytest.raises(TypeError):
        comment_out_line_in_file(path=test_file, line="test", line_ending="\n")


def test_uncomment_line_actual_type_errors(tmp_path):
    """Test actual type errors with real files (lines 1281, 1291, 1312, 1321)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("# line1\nline2\n")

    # Lines 1281, 1291
    with pytest.raises(TypeError):
        uncomment_line_in_file(path="string_not_path", line="test")

    with pytest.raises(TypeError):
        uncomment_line_in_file(path=test_file, line=123)

    # Lines 1312, 1321
    with pytest.raises(TypeError):
        uncomment_line_in_file(path=test_file, line="test", comment_marker=123)

    with pytest.raises(TypeError):
        uncomment_line_in_file(path=test_file, line="test", line_ending="\n")

    with pytest.raises(TypeError):
        uncomment_line_in_file(path=test_file, line="test", multiple="yes")


# =============================================================================
# Lines 638, 657: _ensure_bytes_present error paths
# =============================================================================

def test_ensure_bytes_present_with_make_parents_creates_dirs(tmp_path):
    """Test that make_parents actually creates directories (line 638)."""
    deep_file = tmp_path / "a" / "b" / "c" / "d" / "file.txt"

    # This should execute line 638: path.parent.mkdir(parents=True, exist_ok=True)
    result = filetool.filetool._ensure_bytes_present(
        path=deep_file,
        bytes_payload=b"content\n",
        unique_bytes=False,
        create_if_missing=True,
        make_parents=True,
        line_ending=None,
        comment_marker=None,
        ignore_leading_whitespace=False,
        ignore_trailing_whitespace=False,
    )

    assert result == 8
    assert deep_file.exists()
    assert deep_file.read_bytes() == b"content\n"


# =============================================================================
# Lines 220-237: find_bytes_offset_in_stream - hit ALL branches
# =============================================================================

def test_find_bytes_offset_all_branches():
    """Test all branches in find_bytes_offset_in_stream."""
    from io import BytesIO

    # Line 228: pos != -1 (found)
    stream1 = BytesIO(b"hello world")
    result1 = filetool.filetool.find_bytes_offset_in_stream(stream1, target=b"world")
    assert result1 == 6

    # Line 232: offset += len(chunk)
    stream2 = BytesIO(b"a" * 2000 + b"target" + b"b" * 2000)
    result2 = filetool.filetool.find_bytes_offset_in_stream(stream2, target=b"target", chunk_size=1000)
    assert result2 == 2000

    # Line 233: previous = haystack[-overlap:]
    stream3 = BytesIO(b"x" * 100 + b"TARGET" + b"y" * 100)
    result3 = filetool.filetool.find_bytes_offset_in_stream(stream3, target=b"TARGET", chunk_size=50)
    assert result3 == 100

    # Line 236: return None (not found)
    stream4 = BytesIO(b"no match here")
    result4 = filetool.filetool.find_bytes_offset_in_stream(stream4, target=b"missing")
    assert result4 is None


# =============================================================================
# Lines 561-562, 565, 572-573: ensure_line_in_config_file paths
# =============================================================================

def test_ensure_line_in_config_file_all_paths(tmp_path):
    """Test all code paths in ensure_line_in_config_file."""
    config_file = tmp_path / "config.txt"

    # First call - creates file (line 565-573)
    ensure_line_in_config_file(
        path=config_file,
        line="line1",
        comment_marker="#",
    )
    assert config_file.read_text() == "line1\n"

    # Second call - line already exists (line 561-562: validation passes)
    ensure_line_in_config_file(
        path=config_file,
        line="line1",
        comment_marker="#",
    )
    assert config_file.read_text() == "line1\n"  # No duplicate

    # Test with line containing line_ending - should raise (line 561-562)
    with pytest.raises(ValueError, match="line contains the line_ending delimiter"):
        ensure_line_in_config_file(
            path=config_file,
            line="line1\nline2",
            comment_marker="#",
        )


# =============================================================================
# Run All Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=filetool", "--cov-report=term-missing"])
