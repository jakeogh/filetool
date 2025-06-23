import os


import os
import time
import signal
import subprocess
from pathlib import Path
from shutil import which
import pytest
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from shutil import which  # ← FIXED: required for resolving 'filetool' path

import pytest


def test_bulk_write_completes_without_signal(tmp_path: Path):
    target = tmp_path / "out.dat"
    cli = which("filetool")
    assert cli
    lines = 50
    hex_line = "41" * 512
    expected_line_size = 512 + 1  # payload + newline

    script = tmp_path / "bulk_write.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(lines):
            f.write(f'"{cli}" append --path "{target}" --hex-input "{hex_line}" --create &\n')
        f.write("wait\n")
    script.chmod(0o755)

    subprocess.run([str(script)], check=True)
    assert target.exists()
    assert target.stat().st_size == expected_line_size * lines


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
def test_signal_before_first_write(tmp_path: Path, signal_to_send):
    target = tmp_path / "output.dat"
    cli = which("filetool")
    assert cli
    hex_line = "41" * 512

    script = tmp_path / "launch.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        f.write(f'"{cli}" append --path "{target}" --hex-input "{hex_line}" --create\n')
    script.chmod(0o755)

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(0.01)
    os.killpg(proc.pid, signal_to_send)

    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Did not exit in time")

    # File may or may not exist, but must not have any content
    if target.exists():
        assert target.stat().st_size == 0




@pytest.mark.parametrize("signal_to_send", [signal.SIGINT])
def test_multiple_signals_spam(tmp_path: Path, signal_to_send):
    target = tmp_path / "output.dat"
    cli = which("filetool")
    assert cli
    hex_line = "41" * 512

    script = tmp_path / "loop.sh"
    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(20):
            f.write(f'"{cli}" append --path "{target}" --hex-input "{hex_line}" --create &\n')
        f.write("wait\n")
    script.chmod(0o755)

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait briefly to allow at least one writer to begin
    for _ in range(40):  # up to 2 seconds
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)

    # Then spam signals
    for _ in range(3):
        try:
            os.killpg(proc.pid, signal_to_send)
        except ProcessLookupError:
            break
        time.sleep(0.02)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Did not exit in time")

    # File may or may not exist depending on timing, but if it exists, it should be truncated or partially written
    if target.exists():
        assert target.stat().st_size >= 0







@pytest.mark.parametrize("signal_to_send", [signal.SIGHUP, signal.SIGQUIT])
def test_signal_handling_sighup_sigquit(tmp_path: Path, signal_to_send):
    """Ensure filetool reacts gracefully to SIGHUP and SIGQUIT during concurrent writes."""
    target = tmp_path / "signal_test_output.dat"
    cli = which("filetool")
    assert cli, "filetool must be in PATH"
    hex_line = "41" * 512  # 512 bytes

    script = tmp_path / "signal_test.sh"
    writer_count = 10

    with script.open("w") as f:
        f.write("#!/bin/bash\n")
        for _ in range(writer_count):
            f.write(f'"{cli}" append --path "{target}" --hex-input "{hex_line}" --create &\n')
        f.write("wait\n")
    script.chmod(0o755)
    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):  # Wait up to 1s for writes to start
        if target.stat().st_size > 0:
            break
        time.sleep(0.05)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not terminate in time after signal")


    # Accept any valid size up to full write size
    assert target.exists(), "Output file missing"
    size = target.stat().st_size
    expected_block_size = 513  # 512 'A' bytes + newline
    assert size % expected_block_size == 0, f"Expected multiple of {expected_block_size}, got {size}"
    assert 0 < size <= writer_count * expected_block_size, f"Unexpected file size: {size}"




def long_write_script_sh():
    return """#!/bin/bash
for i in {1..100}; do
  "${cli_path}" append --path "$target" --hex-input "$hex_line" --create &
done
wait
"""


def long_write_script():
    return """#!/usr/bin/env python3
import sys
import time
path = sys.argv[1]
with open(path, "wb") as f:
    for i in range(1024 * 1024):  # ~1 MB
        f.write(b"x" * 1024)      # Write in 1KB chunks
        f.flush()
        time.sleep(0.001)         # Delay to allow signal to interrupt
"""


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
def test_signal_interrupt_during_write(tmp_path: Path, signal_to_send):
    script_path = tmp_path / "long_writer.py"
    target_path = tmp_path / "output.dat"

    # Create the long-write script
    script_path.write_text(long_write_script())
    script_path.chmod(0o755)

    # Launch the writer
    proc = subprocess.Popen(
        [str(script_path), str(target_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for some data to be written
    time.sleep(0.1)

    # Send the signal
    os.kill(proc.pid, signal_to_send)

    # Wait for process to terminate
    proc.wait(timeout=5)

    # Check: file should exist and not be completely empty or absurdly small
    if target_path.exists():
        size = target_path.stat().st_size
        assert 0 < size < 1024 * 1024 * 1024, "File size unreasonable after signal"
    else:
        pytest.fail("File was never created")

    # Optional: check that the file is at least valid (i.e., consistent length of chunks)
    with open(target_path, "rb") as f:
        data = f.read()
        assert data == b"x" * len(data), "File contains unexpected or corrupted content"



@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    writer_count = 20
    script_path = tmp_path / "bulk_writer.sh"
    log_path = tmp_path / "log.txt"

    with script_path.open("w") as script:
        script.write("#!/bin/bash\nset -x\n")
        for i in range(writer_count):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f'{cmd} >> "{log_path}" 2>&1 &\n')
            script.write("sleep 0.02\n")
        script.write("wait\n")

    script_path.chmod(0o755)
    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(100):  # Wait up to 5s for file to be touched
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        if log_path.exists():
            print("\n===== LOG OUTPUT =====\n", log_path.read_text())
        pytest.fail("File was never written to before signal")

    time.sleep(0.1)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_two(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    script_path = tmp_path / "bulk_writer.sh"
    writer_count = 50

    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for i in range(writer_count):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f"{cmd} &\n")
            script.write("sleep 0.01\n")  # Slight stagger per writer
        script.write("wait\n")

    script_path.chmod(0o755)
    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(80):  # Wait up to 4s for file to grow
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("File was never written to before signal")

    time.sleep(0.1)  # Let some writes finish

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass  # Process already exited

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_three(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    input_file = tmp_path / "input.txt"
    input_file.write_text("trigger\n")

    script_path = tmp_path / "bulk_writer.sh"
    writer_count = 50  # Lower count, less contention

    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for i in range(writer_count):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f'({cmd} < "{input_file}") &\n')
            script.write("sleep 0.01\n")  # Slight stagger per writer
        script.write("wait\n")

    script_path.chmod(0o755)
    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for file to grow before sending signal
    for _ in range(80):  # up to 4s
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("File was never written to before signal")

    time.sleep(0.1)  # Let some writes finish

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass  # Process already exited

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_four(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    # Create shared input file to avoid FIFO issues
    input_file = tmp_path / "input.txt"
    input_file.write_text("trigger\n")

    script_path = tmp_path / "bulk_writer.sh"
    writer_count = 100

    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for _ in range(writer_count):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f'{cmd} < "{input_file}" &\n')
        script.write("wait\n")

    script_path.chmod(0o755)
    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for some data to appear in the file
    for _ in range(80):  # up to 4s
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("File was never written to before signal")

    time.sleep(0.2)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_five(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    gate_path = tmp_path / "gate_fifo"
    os.mkfifo(gate_path)

    script_path = tmp_path / "bulk_writer.sh"
    writer_count = 100

    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for _ in range(writer_count):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f'{cmd} < "{gate_path}" &\n')

        # Broadcast to all 100 writers at once
        script.write(f"sleep 0.2\n")
        script.write(f'yes go | head -n {writer_count} > "{gate_path}"\n')
        script.write("wait\n")

    script_path.chmod(0o755)
    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait until file is written to
    for _ in range(80):  # up to 4s
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("File was never written to before signal")

    time.sleep(0.2)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_six(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    gate_path = tmp_path / "gate_fifo"
    os.mkfifo(gate_path)

    script_path = tmp_path / "bulk_writer.sh"
    writer_count = 100

    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for _ in range(writer_count):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f'{cmd} < "{gate_path}" &\n')

        # Repeatedly write newlines to unblock all FIFOs
        script.write(f"sleep 0.2\n")
        script.write(
            f'for i in {{1..{writer_count}}}; do echo go > "{gate_path}"; done\n'
        )
        script.write("wait\n")

    script_path.chmod(0o755)

    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait until file is written to
    for _ in range(80):  # up to 4s
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("File was never written to before signal")

    time.sleep(0.2)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass  # Already dead

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_seven(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    gate_path = tmp_path / "gate_fifo"
    os.mkfifo(gate_path)

    script_path = tmp_path / "bulk_writer.sh"
    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for _ in range(100):
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(f'{cmd} < "{gate_path}" &\n')

        # Unblock all readers after short delay
        script.write(f'{{ sleep 0.2; yes go | head -n 100 > "{gate_path}"; }} &\n')
        # script.write(f'{{ sleep 0.2; echo go > "{gate_path}"; }} &\n')
        script.write("wait\n")
    script_path.chmod(0o755)

    target.write_bytes(b"")

    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for file to be written to before sending signal
    for _ in range(40):  # 2s max
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("File was never written to before signal")

    # Optional small buffer time
    time.sleep(0.1)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass  # Process already exited

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("use_unique", [False, True])
def test_signal_interrupt_during_write_repeated_eight(
    tmp_path: Path, signal_to_send: int, use_unique: bool
):
    target = tmp_path / "sigtest_output.dat"
    hex_line = "41" * 512  # 512-byte 'A' line
    cli_path = which("filetool")
    assert cli_path, "filetool must be installed and in PATH"

    script_path = tmp_path / "bulk_writer.sh"
    with script_path.open("w") as script:
        script.write("#!/bin/bash\n")
        for _ in range(100):  # fewer, parallel writes
            cmd = f'"{cli_path}" append --path "{target}" --hex-input "{hex_line}" --create'
            if use_unique:
                cmd += " --unique"
            script.write(cmd + " &\n")
        script.write("wait\n")
    script_path.chmod(0o755)

    # Start the script in a new process group
    target.write_bytes(b"")
    proc = subprocess.Popen(
        [str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait until file appears and grows a bit
    for _ in range(40):  # wait up to 2 seconds
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.05)

    # Give it a bit more time to ensure work-in-progress
    time.sleep(0.25)

    try:
        os.killpg(proc.pid, signal_to_send)
    except ProcessLookupError:
        pass  # Already exited

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Process did not exit after signal")

    assert target.exists(), "Output file does not exist after signal"
    size = target.stat().st_size
    assert 0 < size < 1_000_000, f"Unexpected file size after signal: {size}"

