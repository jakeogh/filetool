#!/usr/bin/env python3
"""
Final push to cross 90% coverage - COMPLETE VERSION.
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
    _safe_open_rw_binary,
    _modify_file_lines,
    _locked_file_handle,
)
from filetool.test_instrumenter import instrument_function
import filetool.filetool
import filetool.splitlines_bytes


def test_safe_open_rw_binary_raise_on_require_exists():
    """Test line 227: raise in except FileNotFoundError block."""
    nonexistent = Path("/tmp/absolutely_does_not_exist_12345.txt")
    nonexistent.unlink(missing_ok=True)

    with pytest.raises(FileNotFoundError):
        with _safe_open_rw_binary(path=nonexistent, require_exists=True):
            pass


def test_modify_file_lines_replaced_between_stat_and_open(tmp_path):
    """Test line 772: File replaced between stat and open detection."""
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
        time.sleep(0.001)
        test_file.unlink()
        evil_file.rename(test_file)
        attacker_executed.set()

    hooks = {
        "step_6_call__locked_file_handle": trigger_attack,
    }

    instrumented = instrument_function(_modify_file_lines, hooks)
    original_func = filetool.filetool._modify_file_lines
    filetool.filetool._modify_file_lines = instrumented

    try:
        attacker_thread = threading.Thread(target=attacker, daemon=True)
        attacker_thread.start()

        with pytest.raises(OSError, match="was replaced between stat and open"):
            comment_out_line_in_file(
                path=test_file,
                line="line1",
                comment_marker="#",
            )

        attacker_thread.join(timeout=2.0)

    finally:
        filetool.filetool._modify_file_lines = original_func


def test_locked_file_handle_unlock_warning(tmp_path, capsys):
    """Test lines 796-797: Warning on unlock failure."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    original_flock = filetool.filetool.fcntl.flock

    def mock_flock(fd, operation):
        if operation & filetool.filetool.fcntl.LOCK_UN:
            raise OSError(errno.EBADF, "Bad file descriptor")
        return original_flock(fd, operation)

    with patch('filetool.filetool.fcntl.flock', side_effect=mock_flock):
        with _locked_file_handle(
            path=test_file,
            mode="rb+",
            blocking=True,
            create=False,
        ) as fh:
            pass

    captured = capsys.readouterr()
    assert "Warning: failed to unlock" in captured.err


def test_uncomment_content_becomes_line_ending_only(tmp_path):
    """Test line 1312: compare_content.lstrip() becomes line_ending."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("#    \n# line2\nline3\n")

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
