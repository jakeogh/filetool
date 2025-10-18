#!/usr/bin/env python3
"""
Test suite for signal handling in filetool CLI.

These tests verify that filetool handles signals (SIGINT, SIGTERM, etc.) gracefully
during write operations, ensuring data integrity and proper cleanup.
"""

import os
import signal
import subprocess
import time
from pathlib import Path
from shutil import which

import pytest


@pytest.fixture
def cli_path():
    """Get the path to the filetool CLI executable."""
    path = which("filetool")
    if not path:
        pytest.skip("filetool not found in PATH")
    return path


def test_bulk_write_completes_without_signal(tmp_path: Path, cli_path: str):
    """Test that concurrent writes complete successfully without interruption."""
    target = tmp_path / "out.dat"
    lines = 50
    hex_line = "41" * 512  # 512 bytes of 'A'

    script = tmp_path / "bulk_write.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(lines):
            # Use append-bytes (not append) and don't use --create (it doesn't exist)
            f.write(f'"{cli_path}" append-bytes "{hex_line}" --path "{target}" --hex-input &\n')
        f.write("wait\n")
    script.chmod(0o755)

    subprocess.run([str(script)], check=True, timeout=30)
    assert target.exists()
    # Each line is 512 bytes (no newline added by append-bytes)
    assert target.stat().st_size == 512 * lines


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
def test_signal_before_writes_complete(tmp_path: Path, cli_path: str, signal_to_send: int):
    """Test that signal during concurrent writes is handled gracefully."""
    target = tmp_path / "output.dat"
    hex_line = "41" * 512
    writer_count = 20

    script = tmp_path / "launch.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(writer_count):
            f.write(f'"{cli_path}" append-bytes "{hex_line}" --path "{target}" --hex-input &\n')
            f.write("sleep 0.01\n")  # Stagger writes
        f.write("wait\n")
    script.chmod(0o755)

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for some writes to start
    for _ in range(40):  # Wait up to 2s
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)

    # Send signal to process group
    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass  # Already exited

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not terminate after signal")

    # File should exist and contain some data (partial writes are okay)
    if target.exists():
        size = target.stat().st_size
        # Should be a multiple of 512 (block size) due to atomic writes
        assert size % 512 == 0, f"File size not a multiple of block size: {size}"
        assert 0 < size <= writer_count * 512


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_with_unique_mode(
    tmp_path: Path, cli_path: str, signal_to_send: int, use_unique: bool
):
    """Test signal handling with and without --unique flag."""
    target = tmp_path / "output.dat"
    hex_line = "41" * 512
    writer_count = 30

    script = tmp_path / "writer.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(writer_count):
            cmd = f'"{cli_path}" append-bytes "{hex_line}" --path "{target}" --hex-input'
            if use_unique:
                cmd += " --unique"
            f.write(f"{cmd} &\n")
            f.write("sleep 0.02\n")
        f.write("wait\n")
    script.chmod(0o755)

    target.write_bytes(b"")  # Pre-create file

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for writes to begin
    for _ in range(60):
        if target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("No data written before signal")

    time.sleep(0.15)  # Let some writes complete

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists()
    size = target.stat().st_size

    if use_unique:
        # With --unique, should have at most one copy of the data
        assert size <= 512, f"Unique mode wrote more than one block: {size}"
    else:
        # Without --unique, should have some data but not all
        assert 0 < size <= writer_count * 512


@pytest.mark.parametrize("signal_to_send", [signal.SIGHUP, signal.SIGQUIT])
def test_signal_handling_other_signals(tmp_path: Path, cli_path: str, signal_to_send: int):
    """Test handling of SIGHUP and SIGQUIT during writes."""
    target = tmp_path / "output.dat"
    hex_line = "41" * 512
    writer_count = 15

    script = tmp_path / "writer.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(writer_count):
            f.write(f'"{cli_path}" append-bytes "{hex_line}" --path "{target}" --hex-input &\n')
        f.write("wait\n")
    script.chmod(0o755)

    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for writes to start
    for _ in range(30):
        if target.stat().st_size > 0:
            break
        time.sleep(0.05)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not terminate after signal")

    assert target.exists()
    size = target.stat().st_size
    # Verify data is written in complete blocks
    assert size % 512 == 0, f"File size not aligned to block size: {size}"
    assert 0 < size <= writer_count * 512


def test_rapid_signal_spam(tmp_path: Path, cli_path: str):
    """Test that rapid signal delivery doesn't corrupt data."""
    target = tmp_path / "output.dat"
    hex_line = "41" * 512

    script = tmp_path / "writer.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(50):
            f.write(f'"{cli_path}" append-bytes "{hex_line}" --path "{target}" --hex-input &\n')
        f.write("wait\n")
    script.chmod(0o755)

    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for writes to start
    for _ in range(40):
        if target.stat().st_size > 0:
            break
        time.sleep(0.05)

    # Send multiple signals rapidly
    for _ in range(5):
        try:
            os.killpg(proc.pid, signal.SIGINT)
            time.sleep(0.02)
        except ProcessLookupError:
            break

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    if target.exists():
        size = target.stat().st_size
        # Data should still be block-aligned
        assert size % 512 == 0, f"Corrupted file size after signal spam: {size}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
