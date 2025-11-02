#!/usr/bin/env python3
"""
CORRECT TEST FOR LINE 1312 - The ELSE branch!

Line 1312 is: compare_content = stripped
This happens when:
- stripped != line_ending (it's not just a newline)
- len(stripped) > 0 (it's not empty)
- So we have actual content after stripping leading whitespace
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_else_branch():
    """
    Line 1312: compare_content = stripped (the ELSE branch)

    We need a commented line where after removing "# " and lstripping,
    we have actual content (not just line_ending, not empty).

    Example: "#   target\n"
    - Remove "# ": "  target\n"
    - lstrip(): "target\n"
    - This is NOT line_ending, NOT empty
    - So we take the else branch: compare_content = stripped
    """
    test_file = Path("/tmp/test_1312_else.txt")

    # Key: Content with leading spaces AFTER the comment marker
    test_file.write_text("#   target\nother\n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        print(f"Result: {result}")
        print(f"Final content: {test_file.read_text()!r}")

        assert result == 1

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    import subprocess
    import sys

    print("=== Running test with coverage on line 1312 ===")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v", "-s",
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
    ])
    sys.exit(result.returncode)
