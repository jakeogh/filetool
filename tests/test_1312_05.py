#!/usr/bin/env python3
"""
HIT LINE 1312 - The REAL line!

Line 1312: compare_content = line_ending

This happens when:
1. We're processing a commented line
2. ignore_leading_whitespace=True
3. content_after_marker.lstrip() == line_ending
   (i.e., only whitespace + newline after comment marker)
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_whitespace_after_comment():
    """
    Line 1312: compare_content = line_ending

    Need: "# <whitespace>\n" where after stripping we get just "\n"
    Example: "#   \n" -> remove "# " -> "  \n" -> lstrip() -> "\n"
    """
    test_file = Path("/tmp/test_1312_real.txt")

    # File with a commented line that's just whitespace
    # AND our actual target line
    test_file.write_bytes(b"#   \n# target\n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,  # Line 1309
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
    print("Testing line 1312: compare_content = line_ending")
    print("="*60)

    result = subprocess.run([
        sys.executable, "-m", "pytest", __file__,
        "-v", "-s",
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
    ])
