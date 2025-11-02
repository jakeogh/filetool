#!/usr/bin/env python3
"""
LINE 1312 IS: if ignore_trailing_whitespace:

This line is AFTER the leading whitespace block.
Why isn't it being hit?

The only way to NOT hit line 1312 is if we never enter the
'if compare_line.startswith(comment_prefix):' block at line 1299.

So the commented line must NOT start with comment_prefix!
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_trailing_check(tmp_path):
    """
    Line 1312: if ignore_trailing_whitespace:

    This is checked for EVERY commented line that starts with comment_prefix.
    We need a file where:
    1. A line starts with "# " (comment_prefix)
    2. We're trying to uncomment it
    3. ignore_trailing_whitespace=True
    """
    test_file = tmp_path / "test.txt"

    # Simple commented line
    test_file.write_text("# myline\n")

    result = uncomment_line_in_file(
        path=test_file,
        line="myline",
        comment_marker="#",
        ignore_leading_whitespace=False,  # Try False
        ignore_trailing_whitespace=True,  # This should hit line 1312
    )

    assert result == 1


def test_line_1312_both_flags(tmp_path):
    """
    Try with both flags True.
    """
    test_file = tmp_path / "test.txt"

    test_file.write_text("# myline\n")

    result = uncomment_line_in_file(
        path=test_file,
        line="myline",
        comment_marker="#",
        ignore_leading_whitespace=True,   # Line 1306: True
        ignore_trailing_whitespace=True,  # Line 1312: True
    )

    assert result == 1


if __name__ == "__main__":
    import subprocess
    import sys

    result = subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v", "-s",
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
        "-k", "1312"
    ])

    print("\n" + "="*60)
    print("Check if line 1312 is now covered!")
    print("="*60)

    sys.exit(result.returncode)
