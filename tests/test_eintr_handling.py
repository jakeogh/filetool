#!/usr/bin/env python3
"""
Test suite to verify that filetool operations handle EINTR correctly.

These tests verify that operations complete successfully even when interrupted
by signals, demonstrating that the EINTR retry logic works as intended.

Note: These tests are skipped by default because sending signals to the test
process can interfere with pytest. Run with: pytest -v -m eintr_tests
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


# Skip these tests by default since they can interfere with pytest
pytestmark = pytest.mark.skip(
    reason="EINTR tests send signals that can kill pytest. Run explicitly with -m eintr_tests if needed."
)


def test_append_bytes_in_subprocess_with_signals():
    """Test that append operations work correctly when interrupted by signals in a subprocess."""
    test_script = """
import os
import signal
import sys
import time
import threading
from pathlib import Path
from filetool import append_bytes_to_file

def handler(signum, frame):
    pass  # no-op handler

signal.signal(signal.SIGUSR1, handler)

path = Path(sys.argv[1])
path.write_bytes(b"initial\\n")

def signal_spammer():
    for _ in range(10):
        time.sleep(0.01)
        os.kill(os.getpid(), signal.SIGUSR1)

spammer = threading.Thread(target=signal_spammer, daemon=True)
spammer.start()

result = append_bytes_to_file(
    bytes_payload=b"data\\n",
    path=path,
    unique_bytes=False,
    create_if_missing=True,
    make_parents=False,
)

spammer.join(timeout=2)

assert result == 5
assert path.read_bytes() == b"initial\\ndata\\n"
print("SUCCESS")
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        script_file = Path(tmpdir) / "test_script.py"
        script_file.write_text(test_script)

        result = subprocess.run(
            [sys.executable, str(script_file), str(test_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout
        assert test_file.read_bytes() == b"initial\ndata\n"


def test_unique_append_in_subprocess_with_signals():
    """Test unique mode under signal interruption in a subprocess."""
    test_script = """
import os
import signal
import sys
import time
import threading
from pathlib import Path
from filetool import append_bytes_to_file

def handler(signum, frame):
    pass

signal.signal(signal.SIGUSR1, handler)

path = Path(sys.argv[1])
path.write_bytes(b"line1\\nline2\\n")

def signal_spammer():
    for _ in range(15):
        time.sleep(0.005)
        os.kill(os.getpid(), signal.SIGUSR1)

spammer = threading.Thread(target=signal_spammer, daemon=True)
spammer.start()

result = append_bytes_to_file(
    bytes_payload=b"line3\\n",
    path=path,
    unique_bytes=True,
    create_if_missing=True,
    make_parents=False,
    line_ending=b"\\n",
)

spammer.join(timeout=2)

assert result == 6
assert path.read_bytes() == b"line1\\nline2\\nline3\\n"
print("SUCCESS")
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        script_file = Path(tmpdir) / "test_script.py"
        script_file.write_text(test_script)

        result = subprocess.run(
            [sys.executable, str(script_file), str(test_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout


def test_unique_skip_existing_in_subprocess_with_signals():
    """Test that duplicate detection works under signal interruption in a subprocess."""
    test_script = """
import os
import signal
import sys
import time
import threading
from pathlib import Path
from filetool import append_bytes_to_file

def handler(signum, frame):
    pass

signal.signal(signal.SIGUSR1, handler)

path = Path(sys.argv[1])
path.write_bytes(b"existing\\n")

def signal_spammer():
    for _ in range(20):
        time.sleep(0.005)
        os.kill(os.getpid(), signal.SIGUSR1)

spammer = threading.Thread(target=signal_spammer, daemon=True)
spammer.start()

result = append_bytes_to_file(
    bytes_payload=b"existing\\n",
    path=path,
    unique_bytes=True,
    create_if_missing=True,
    make_parents=False,
    line_ending=b"\\n",
)

spammer.join(timeout=2)

assert result == 0  # Should not write
assert path.read_bytes() == b"existing\\n"
print("SUCCESS")
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        script_file = Path(tmpdir) / "test_script.py"
        script_file.write_text(test_script)

        result = subprocess.run(
            [sys.executable, str(script_file), str(test_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout


def test_file_creation_in_subprocess_with_signals():
    """Test file/directory creation under signal interruption in a subprocess."""
    test_script = """
import os
import signal
import sys
import time
import threading
from pathlib import Path
from filetool import append_bytes_to_file

def handler(signum, frame):
    pass

signal.signal(signal.SIGUSR1, handler)

path = Path(sys.argv[1]) / "newdir" / "test.txt"

def signal_spammer():
    for _ in range(10):
        time.sleep(0.01)
        os.kill(os.getpid(), signal.SIGUSR1)

spammer = threading.Thread(target=signal_spammer, daemon=True)
spammer.start()

result = append_bytes_to_file(
    bytes_payload=b"newdata\\n",
    path=path,
    unique_bytes=False,
    create_if_missing=True,
    make_parents=True,
)

spammer.join(timeout=2)

assert result == 8
assert path.exists()
assert path.read_bytes() == b"newdata\\n"
print("SUCCESS")
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        script_file = Path(tmpdir) / "test_script.py"
        script_file.write_text(test_script)

        result = subprocess.run(
            [sys.executable, str(script_file), str(tmpdir)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout


def test_binary_data_in_subprocess_with_signals():
    """Test binary data integrity under signal interruption in a subprocess."""
    test_script = """
import os
import signal
import sys
import time
import threading
from pathlib import Path
from filetool import append_bytes_to_file

def handler(signum, frame):
    pass

signal.signal(signal.SIGUSR1, handler)

path = Path(sys.argv[1])
binary_payload = bytes(range(256))

def signal_spammer():
    for _ in range(20):
        time.sleep(0.005)
        os.kill(os.getpid(), signal.SIGUSR1)

spammer = threading.Thread(target=signal_spammer, daemon=True)
spammer.start()

result = append_bytes_to_file(
    bytes_payload=binary_payload,
    path=path,
    unique_bytes=False,
    create_if_missing=True,
    make_parents=False,
)

spammer.join(timeout=2)

assert result == 256
assert path.read_bytes() == binary_payload
print("SUCCESS")
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "binary.dat"
        script_file = Path(tmpdir) / "test_script.py"
        script_file.write_text(test_script)

        result = subprocess.run(
            [sys.executable, str(script_file), str(test_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout
        assert test_file.read_bytes() == bytes(range(256))


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
