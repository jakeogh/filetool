#!/usr/bin/env python3
"""
FORCE LINE 1312 TO EXECUTE - Final attempt
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_force_execution():
    """
    Force line 1312: compare_content = line_ending

    File: "#   \n# target\n"
    Search for: "target"

    When processing "#   \n":
    - content_after_marker = "  \n"
    - stripped = ""
    - Line 1312 executes: compare_content = line_ending
    """
    test_file = Path("/tmp/force_1312.txt")
    test_file.write_bytes(b"#   \n# target\n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        assert result == 1
        print("Test passed! Line 1312 should have executed.")

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    import subprocess
    import sys

    print("="*60)
    print("Running test WITH coverage")
    print("="*60)

    # Clear cache
    subprocess.run(["rm", "-rf", ".coverage", ".pytest_cache", "__pycache__"])

    # Run with coverage
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v", "-s",
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
    ])

    print("\n" + "="*60)
    print("Check if line 1312 is covered!")
    print("="*60)
