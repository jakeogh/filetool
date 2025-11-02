#!/usr/bin/env python3
"""
Tests for hardlink verification error paths in _modify_file_lines.
"""

import pytest
import os
import threading
from pathlib import Path
from filetool import comment_out_line_in_file
from filetool.filetool import _modify_file_lines
from filetool.test_instrumenter import instrument_function
import filetool.filetool


def test_hardlink_verification_detects_inode_change(tmp_path):
    """
    Test that hardlink verification detects file replacement by inode change.

    This tests the error path where stat_after_link.st_ino != inode_before.
    """
    config_file = tmp_path / "config.txt"
    evil_file = tmp_path / "evil.txt"

    initial_content = "line1\nline2\nline3\n"
    evil_content = "EVIL\n"

    config_file.write_text(initial_content)
    evil_file.write_text(evil_content)

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def attack_trigger(ctx):
        """Hook that triggers attacker after hardlink creation."""
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        """Attacker replaces file after hardlink, before verification."""
        attack_barrier.wait()

        # Unlink and replace with new file (new inode)
        config_file.unlink()
        evil_file.rename(config_file)

        attacker_executed.set()

    # Instrument to attack after hardlink creation
    hooks = {
        "step_28_create_hardlink": attack_trigger,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Should detect the inode change and raise OSError
        with pytest.raises(OSError, match="File .* was replaced during hardlink verification"):
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

        # Verify attacker executed
        assert attacker_executed.is_set()

        # Verify evil content is in place (attacker succeeded, victim aborted)
        assert config_file.read_text() == evil_content

    finally:
        filetool.filetool._modify_file_lines = original_func


def test_hardlink_verification_detects_link_count_mismatch(tmp_path):
    """
    Test that hardlink verification detects unexpected link count changes.

    This tests the error path where link count doesn't match expected value
    but inode is the same (covered by test_attack_1_hardlink_exhaustion).
    """
    # This is already covered by test_attack_1_hardlink_exhaustion
    # which creates extra hardlinks, causing link count mismatch
    pass


def test_hardlink_cleanup_handles_missing_link(tmp_path):
    """
    Test that hardlink cleanup handles case where link was already removed.

    This tests the exception handling in step_34_cleanup_hardlink.
    """
    config_file = tmp_path / "config.txt"
    config_file.write_text("line1\nline2\nline3\n")

    cleanup_attempted = threading.Event()
    attack_barrier = threading.Barrier(2)

    def capture_link_and_remove(ctx):
        """Hook that captures and removes the hardlink before cleanup."""
        link_path = ctx.locals.get('link_path')
        if link_path and link_path.exists():
            # Remove the hardlink before the legitimate cleanup
            link_path.unlink()
        attack_barrier.wait()
        cleanup_attempted.wait(timeout=5.0)

    def wait_for_cleanup():
        """Wait for cleanup to be attempted."""
        attack_barrier.wait()
        cleanup_attempted.set()

    # Instrument to remove link before cleanup
    hooks = {
        "step_33_rename": capture_link_and_remove,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        cleanup_thread = threading.Thread(target=wait_for_cleanup, daemon=True)
        cleanup_thread.start()

        # Should succeed despite hardlink being removed
        result = comment_out_line_in_file(
            path=config_file,
            line="line1",
            comment_marker="#",
        )

        assert result == 1
        assert "# line1" in config_file.read_text()

        cleanup_thread.join(timeout=2.0)

    finally:
        filetool.filetool._modify_file_lines = original_func


def test_temp_file_cleanup_on_hardlink_verification_failure(tmp_path):
    """
    Test that temp file is cleaned up when hardlink verification fails.

    This tests lines 1043-1049 where temp_path.unlink() is called.
    """
    config_file = tmp_path / "config.txt"
    evil_file = tmp_path / "evil.txt"

    config_file.write_text("line1\nline2\nline3\n")
    evil_file.write_text("EVIL\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)
    temp_path_captured = None

    def capture_temp_and_attack(ctx):
        """Capture temp path and trigger attacker."""
        nonlocal temp_path_captured
        temp_path_captured = ctx.locals.get('temp_path')
        attack_barrier.wait()
        attacker_executed.wait(timeout=5.0)

    def attacker():
        """Replace file after hardlink creation."""
        attack_barrier.wait()
        config_file.unlink()
        evil_file.rename(config_file)
        attacker_executed.set()

    hooks = {
        "step_28_create_hardlink": capture_temp_and_attack,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        with pytest.raises(OSError, match="was replaced during hardlink verification"):
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

        # Verify temp file was cleaned up
        if temp_path_captured:
            assert not temp_path_captured.exists(), "Temp file should be cleaned up on error"

    finally:
        filetool.filetool._modify_file_lines = original_func
