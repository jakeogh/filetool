#!/usr/bin/env python3
"""
DEBUG LINE 1312 - Prove it's hit with instrumentation
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_with_trace():
    """
    Add explicit trace to prove line 1312 executes.
    """
    test_file = Path("/tmp/test_1312_trace.txt")

    # Create file where last line has no newline
    test_file.write_bytes(b"# goodline\n# badline")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="goodline",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        print(f"Result: {result}")
        print(f"Content: {test_file.read_bytes()!r}")

        assert result == 1

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    import subprocess
    import sys

    print("="*60)
    print("STEP 1: Run without coverage (prove it works)")
    print("="*60)
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v", "-s"])

    print("\n" + "="*60)
    print("STEP 2: Clear coverage cache")
    print("="*60)
    subprocess.run(["rm", "-rf", ".coverage", ".pytest_cache"])

    print("\n" + "="*60)
    print("STEP 3: Run WITH coverage (fresh)")
    print("="*60)
    subprocess.run([
        sys.executable, "-m", "pytest", __file__,
        "-v", "-s",
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
        "--cov-branch"  # Branch coverage too!
    ])

    print("\n" + "="*60)
    print("STEP 4: Check if line 1312 is covered")
    print("="*60)
    subprocess.run([
        sys.executable, "-m", "coverage", "report",
        "--show-missing",
        "filetool/filetool.py"
    ])
