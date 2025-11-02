#!/usr/bin/env python3
"""
LASER-FOCUSED TEST FOR LINE 1312 - Standalone Investigation
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_precise():
    """
    Line 1312: compare_content = line_ending

    This happens when:
    - We have a commented line: "# <content>\n"
    - We remove the "# " prefix to get "<content>\n"
    - ignore_leading_whitespace=True, so we call lstrip()
    - After lstrip(), we get just "\n" (the line_ending)
    - Line 1311 checks: if stripped == line_ending
    - Line 1312: compare_content = line_ending
    """
    test_file = Path("/tmp/test_1312_precise.txt")

    # Content with ONLY whitespace after comment marker
    test_file.write_text("# \n# target\n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        assert result == 1

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    # Run with coverage to see if line 1312 is hit
    import subprocess
    import sys

    print("=== Running test with coverage ===")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v",
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
        "-k", "1312"
    ])
    sys.exit(result.returncode)
