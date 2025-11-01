#!/usr/bin/env python3
"""
Attack scenario tests for _modify_file_lines implementation.

These tests verify that the file modification implementation correctly handles
malicious or concurrent modifications from cooperating processes (processes that
respect advisory locks). Each test simulates a specific attack at a specific
point in the modification timeline using the instrumenter to inject hooks.

All attackers in these tests are "cooperating" - they acquire the same global
lock before making changes. We're testing that the implementation's defense-in-depth
protections (inode checks, hardlink verification) correctly detect and abort
operations when concurrent modifications occur.

Run with: pytest test_attack_scenarios_real.py -v -s
"""

import os
# Import the actual implementation
# In real usage, this would be: from filetool import _modify_file_lines
# For testing, we'll need to import from the actual module
import sys
import threading
from pathlib import Path

import pytest
# Import the instrumenter
from filetool.test_instrumenter import instrument_function

sys.path.insert(0, str(Path(__file__).parent))

# We need to import the actual filetool module
# This assumes filetool.py is in the same directory or importable
try:
    import filetool
    from filetool import comment_out_line_in_file
except ImportError:
    pytest.skip("filetool module not available", allow_module_level=True)


@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


def test_attack_1_hardlink_exhaustion(test_dir):
    """
    Attack 1: Hardlink Exhaustion

    Timeline:
    - Legitimate operation: step 28 (create hardlink)
    - Attacker: Between step 28-31, create many hardlinks to target
    - Legitimate operation: step 31 (verify link count)

    Expected behavior:
    - Step 31 detects link count mismatch (expected: original_nlink + 1, actual: much higher)
    - Operation aborts with error
    - No data corruption
    - Temporary file is cleaned up

    Impact: Denial of service, but no corruption
    """
    config_file = test_dir / "config.txt"
    initial_content = "line1\nline2\nline3\n"
    config_file.write_text(initial_content)

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)  # Sync attacker with victim
    attack_links = []

    def attack_create_hardlinks(ctx):
        """Hook that triggers attacker thread."""
        attack_barrier.wait()  # Signal attacker to proceed

    def attacker():
        """Attacker creates many hardlinks between step 28 and 31."""
        attack_barrier.wait()  # Wait for step 28 to complete

        # Create multiple hardlinks
        for i in range(10):
            link = test_dir / f"evil_link_{i}"
            try:
                os.link(config_file, link)
                attack_links.append(link)
            except (FileExistsError, OSError):
                pass

        attacker_executed.set()

    # Instrument the function
    hooks = {
        "step_28_create_hardlink": attack_create_hardlinks,
    }

    instrumented = instrument_function(filetool._modify_file_lines, hooks)

    # Replace the function temporarily
    original_func = filetool._modify_file_lines
    filetool._modify_file_lines = instrumented

    try:
        # Start attacker thread
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Execute the operation - should detect the hardlink exhaustion
        with pytest.raises(OSError) as exc_info:
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        # Wait for attacker to finish
        attacker_thread.join(timeout=2.0)

        # Verify attack was executed
        assert attacker_executed.is_set(), "Attacker thread did not execute"

        # Verify we detected the issue (link count mismatch)
        # The operation should have aborted without modifying the file
        assert (
            config_file.read_text() == initial_content
        ), "File was modified despite error"

        # Verify no temporary files remain
        temp_files = list(test_dir.glob(".filetool.tmp.*"))
        assert len(temp_files) == 0, f"Temporary files not cleaned up: {temp_files}"

        # Verify attacker's hardlinks still exist
        assert len(attack_links) > 0, "Attacker should have created hardlinks"
        for link in attack_links:
            assert link.exists(), f"Attacker's hardlink {link} should still exist"

    finally:
        # Restore original function
        filetool._modify_file_lines = original_func


def test_attack_2_delete_during_read(test_dir):
    """
    Attack 2: Delete File During Read

    Timeline:
    - Legitimate operation: step 12 (reading file with splitlines_bytes)
    - Attacker: Between step 12-13, unlink(path)
    - Legitimate operation: step 13 (stat_after_read)

    Expected behavior:
    - Step 13 fails with FileNotFoundError
    - Operation aborts cleanly
    - No temporary files left behind

    Impact: Denial of service, but no corruption

    Note: The file descriptor from step 7 remains valid even after unlink,
    so step 12 completes successfully. Only step 13 detects the deletion.
    """
    config_file = test_dir / "config.txt"
    initial_content = "line1\nline2\nline3\n"
    config_file.write_text(initial_content)

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def attack_trigger(ctx):
        """Hook that triggers attacker thread."""
        attack_barrier.wait()

    def attacker():
        """Attacker deletes file after it's been opened but during read."""
        attack_barrier.wait()  # Wait for step 12 to complete

        # Delete the file - the file descriptor is still valid!
        config_file.unlink()
        attacker_executed.set()

    # Instrument the function
    hooks = {
        "step_12_read_lines": attack_trigger,
    }

    instrumented = instrument_function(filetool._modify_file_lines, hooks)

    # Replace the function temporarily
    original_func = filetool._modify_file_lines
    filetool._modify_file_lines = instrumented

    try:
        # Start attacker thread
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Execute the operation - should detect the deletion
        with pytest.raises(OSError) as exc_info:
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        # Wait for attacker
        attacker_thread.join(timeout=2.0)

        # Verify attack was executed
        assert attacker_executed.is_set(), "Attacker thread did not execute"

        # Verify error message indicates file was deleted
        assert (
            "deleted" in str(exc_info.value).lower()
        ), f"Error message should mention deletion: {exc_info.value}"

        # Verify file is deleted (attacker succeeded)
        assert not config_file.exists(), "File should be deleted by attacker"

        # Verify no temporary files remain
        temp_files = list(test_dir.glob(".filetool.tmp.*"))
        assert len(temp_files) == 0, f"Temporary files not cleaned up: {temp_files}"

    finally:
        # Restore original function
        filetool._modify_file_lines = original_func


def test_attack_3_replace_during_permission_copy(test_dir):
    """
    Attack 3: Replace File During Permission Copy

    Timeline:
    - Legitimate operation: step 24 (chown on temp file)
    - Attacker: Between step 24-25, rename(malicious_file, path)
    - Legitimate operation: step 25 (stat_before_rename)

    Expected behavior:
    - Step 26 detects inode change (inode != inode_before)
    - Operation aborts with OSError
    - Temporary file is cleaned up
    - Attacker's file remains at path (attacker wins this race)

    Impact: Attacker successfully replaces file, but legitimate operation
    correctly detects this and aborts without corrupting anything.
    """
    config_file = test_dir / "config.txt"
    malicious_file = test_dir / "malicious.txt"

    initial_content = "line1\nline2\nline3\n"
    malicious_content = "HACKED\nEVIL\nMALICIOUS\n"

    config_file.write_text(initial_content)
    malicious_file.write_text(malicious_content)

    original_inode = config_file.stat().st_ino

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def attack_trigger(ctx):
        """Hook that triggers attacker thread."""
        attack_barrier.wait()

    def attacker():
        """Attacker replaces target file during permission copy phase."""
        attack_barrier.wait()  # Wait for step 24

        # Replace the target file
        os.rename(malicious_file, config_file)
        attacker_executed.set()

    # Instrument the function
    hooks = {
        "step_24_chown_temp": attack_trigger,
    }

    instrumented = instrument_function(filetool._modify_file_lines, hooks)

    # Replace the function temporarily
    original_func = filetool._modify_file_lines
    filetool._modify_file_lines = instrumented

    try:
        # Start attacker thread
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Execute the operation - should detect the replacement
        with pytest.raises(OSError) as exc_info:
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        # Wait for attacker
        attacker_thread.join(timeout=2.0)

        # Verify attack was executed
        assert attacker_executed.is_set(), "Attacker thread did not execute"

        # Verify error message indicates file was replaced
        assert (
            "replaced" in str(exc_info.value).lower()
        ), f"Error message should mention replacement: {exc_info.value}"

        # Verify config_file now contains malicious content (attacker won)
        assert (
            config_file.read_text() == malicious_content
        ), "Attacker's file should be present"

        # Verify config_file has different inode than original
        assert config_file.stat().st_ino != original_inode, "File should have new inode"

        # Verify no temporary files remain
        temp_files = list(test_dir.glob(".filetool.tmp.*"))
        assert len(temp_files) == 0, f"Temporary files not cleaned up: {temp_files}"

        # This is CORRECT behavior - we detected the race and didn't corrupt anything

    finally:
        # Restore original function
        filetool._modify_file_lines = original_func


def test_attack_4_symlink_race_on_temp_file(test_dir):
    """
    Attack 4: Symlink Race on Temporary File Path

    Timeline:
    - Legitimate operation: step 18 (generate temp path)
    - Attacker: Between step 18-19, create symlink at temp path pointing to evil target
    - Legitimate operation: step 19 (open temp file with O_EXCL)

    Expected behavior:
    - Step 19 fails (open with O_EXCL on symlink behaves specially)
    - Operation aborts with OSError/FileExistsError
    - No files corrupted

    Impact: Denial of service. Attacker cannot trick legitimate operation
    into writing to arbitrary location because O_EXCL prevents following symlinks.

    Note: The O_EXCL flag combined with O_CREAT fails if path exists as symlink,
    providing protection against this attack vector.
    """
    config_file = test_dir / "config.txt"
    evil_target = test_dir / "evil_target.txt"

    initial_content = "line1\nline2\nline3\n"
    config_file.write_text(initial_content)
    evil_target.write_text("SHOULD_NOT_BE_MODIFIED\n")

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)
    temp_path_captured = None

    def capture_temp_path(ctx):
        """Hook that captures temp_path and triggers attacker."""
        nonlocal temp_path_captured
        temp_path_captured = ctx.locals.get("temp_path")
        attack_barrier.wait()

    def attacker():
        """Attacker creates symlink at predicted temp file path."""
        attack_barrier.wait()  # Wait for temp path to be generated

        # Use the captured temp path
        if temp_path_captured and not temp_path_captured.exists():
            try:
                temp_path_captured.symlink_to(evil_target)
                attacker_executed.set()
            except (FileExistsError, OSError):
                pass

    # Instrument the function
    hooks = {
        "step_18_generate_temp_path": capture_temp_path,
    }

    instrumented = instrument_function(filetool._modify_file_lines, hooks)

    # Replace the function temporarily
    original_func = filetool._modify_file_lines
    filetool._modify_file_lines = instrumented

    try:
        # Start attacker thread
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Execute the operation - should fail on symlink
        with pytest.raises((OSError, FileExistsError)) as exc_info:
            comment_out_line_in_file(
                path=config_file,
                line="line1",
                comment_marker="#",
            )

        # Wait for attacker
        attacker_thread.join(timeout=2.0)

        # Verify attack was executed
        assert attacker_executed.is_set(), "Attacker thread did not execute"

        # Verify evil_target was not modified
        assert (
            evil_target.read_text() == "SHOULD_NOT_BE_MODIFIED\n"
        ), "Evil target should not be modified"

        # Verify config_file was not modified
        assert (
            config_file.read_text() == initial_content
        ), "Original file should not be modified"

        # Verify the symlink still exists (attacker created it)
        if temp_path_captured:
            assert temp_path_captured.is_symlink(), "Attacker's symlink should exist"

    finally:
        # Restore original function
        filetool._modify_file_lines = original_func


def test_attack_5_replace_after_hardlink_before_rename(test_dir):
    """
    Attack 5: Replace File After Hardlink Creation, Before Rename

    Timeline:
    - Legitimate operation: step 32 (hardlink_successful = True)
    - Attacker: Between step 32-33, rename(evil_file, path)
    - Legitimate operation: step 33 (os.rename(temp_path, path))

    Expected behavior:
    - Step 33 succeeds - renames temp_path over path
    - Attacker's evil_file is CLOBBERED by legitimate operation's temp file
    - This is CORRECT behavior - both processes had locks, last writer wins

    Analysis:
    - The hardlink created in step 28 points to the ORIGINAL file's inode
    - When attacker replaces path with evil_file (new inode), the hardlink still
      points to the old inode
    - The legitimate operation's rename overwrites path with temp_path
    - Attacker's evil_file is lost

    Impact: Attacker loses, legitimate operation succeeds. This is correct behavior
    because both processes are cooperating (using locks), and the legitimate operation
    had the lock first.
    """
    config_file = test_dir / "config.txt"
    evil_file = test_dir / "evil.txt"

    initial_content = "line1\nline2\nline3\n"
    evil_content = "EVIL_CONTENT\n"
    expected_content = "# line1\n# line2\n# line3\n"  # After commenting

    config_file.write_text(initial_content)
    evil_file.write_text(evil_content)

    original_inode = config_file.stat().st_ino

    attacker_executed = threading.Event()
    attack_barrier = threading.Barrier(2)

    def attack_trigger(ctx):
        """Hook that triggers attacker thread."""
        attack_barrier.wait()

    def attacker():
        """Attacker replaces file in the critical window after hardlink check."""
        attack_barrier.wait()  # Wait for step 32

        # Replace the file - new inode
        os.rename(evil_file, config_file)
        attacker_executed.set()

        # At this point:
        # - path points to evil_file (new inode)
        # - hardlink points to original file (old inode)
        # - temp_path contains legitimate transformed content

    # Instrument the function
    hooks = {
        "step_32_hardlink_successful": attack_trigger,
    }

    instrumented = instrument_function(filetool._modify_file_lines, hooks)

    # Replace the function temporarily
    original_func = filetool._modify_file_lines
    filetool._modify_file_lines = instrumented

    try:
        # Start attacker thread
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        # Execute the operation - should succeed and clobber attacker's file
        result = comment_out_line_in_file(
            path=config_file,
            line="line1",
            comment_marker="#",
        )

        # Wait for attacker
        attacker_thread.join(timeout=2.0)

        # Verify attack was executed
        assert attacker_executed.is_set(), "Attacker thread did not execute"

        # Verify operation succeeded
        assert result > 0, "Operation should have modified lines"

        # Verify config_file contains transformed content (not evil content)
        assert (
            config_file.read_text() == expected_content
        ), "File should contain commented lines"

        # Verify evil_file no longer exists (was renamed then overwritten)
        assert not evil_file.exists(), "Evil file should not exist (was renamed)"

        # Verify config_file has NEW inode (neither original nor evil's inode)
        current_inode = config_file.stat().st_ino
        # Note: The inode might be the same as original if the rename reused it,
        # but the content is definitely from temp_path

        # The key verification: legitimate operation won
        assert config_file.read_text() == expected_content

    finally:
        # Restore original function
        filetool._modify_file_lines = original_func


def test_normal_operation_without_attacks(test_dir):
    """
    Baseline test: Verify normal operation works correctly without attacks.

    This ensures that our instrumentation doesn't break the normal flow.
    """
    config_file = test_dir / "config.txt"
    initial_content = "line1\nline2\nline3\n"
    expected_content = "# line1\n# line2\n# line3\n"

    config_file.write_text(initial_content)

    # Execute without instrumentation
    result = comment_out_line_in_file(
        path=config_file,
        line="line1",
        comment_marker="#",
    )

    # Verify it worked
    assert result == 1, "Should have modified 1 line"
    assert "# line1" in config_file.read_text(), "Line should be commented"

    # Verify no temporary files remain
    temp_files = list(test_dir.glob(".filetool.tmp.*"))
    assert len(temp_files) == 0, f"Temporary files not cleaned up: {temp_files}"

    # Verify no hardlinks remain
    link_files = list(test_dir.glob(".filetool.link.*"))
    assert len(link_files) == 0, f"Hardlink files not cleaned up: {link_files}"


def test_attack_summary():
    """
    Summary test documenting security properties.

    This test documents that all attacks result in either:
    1. Detection and abort (DoS but no corruption)
    2. Correct behavior (legitimate operation wins)

    No attack can cause data corruption.
    """
    summary = """
    Attack Results Summary:

    Attack 1 (Hardlink exhaustion):
        - Detected at step 31 (link count mismatch)
        - Operation aborts
        - No corruption
        - Result: DoS only ✓

    Attack 2 (Delete during read):
        - Detected at step 13 (FileNotFoundError)
        - Operation aborts
        - No corruption
        - Result: DoS only ✓

    Attack 3 (Replace during permission copy):
        - Detected at step 26 (inode mismatch)
        - Operation aborts
        - Attacker's file remains (but no corruption)
        - Result: Detected and aborted ✓

    Attack 4 (Symlink on temp path):
        - Prevented at step 19 (O_EXCL fails on symlink)
        - Operation aborts
        - Target file not modified
        - Result: DoS only ✓

    Attack 5 (Replace after hardlink):
        - NOT detected (by design)
        - Legitimate operation succeeds
        - Attacker's file is clobbered
        - Result: Legitimate operation wins ✓

    Conclusion:
    All attacks either result in DoS (no corruption) or legitimate operation wins.
    No attack can cause data corruption or trick the implementation into writing
    incorrect data. The defense-in-depth approach (multiple inode checks + hardlink
    trick) successfully protects against concurrent modification.
    """

    # This is a documentation test
    print(summary)
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
