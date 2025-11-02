#!/usr/bin/env python3
"""
HIT LINE 1312 - CORRECT VERSION

Line 1312: compare_content = line_ending

We need: content_after_marker that after lstrip() equals just line_ending

Example: "# \n" (comment + space + newline)
After removing "# ": " \n" (just space + newline)
After lstrip(): "\n" (just newline)
Now: stripped == line_ending is TRUE!
Line 1312 executes!
"""

import sys
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_only_whitespace():
    """
    Line 1312: compare_content = line_ending

    File content: "# \n" where after "# " removal we get " \n"
    After lstrip: "\n" which equals line_ending!
    """
    test_file = Path("/tmp/test_1312_final.txt")

    # Key: "# \n" - after removing "# " we get " \n", after lstrip we get "\n"
    # But we also need our target line
    test_file.write_bytes(b"# \n# target\n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line="target",
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        print(f"Result: {result}")
        assert result == 1

    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    import subprocess

    print("Testing with trace:")
    test_line_1312_only_whitespace()

    print("\n" + "="*60)
    print("Now testing with coverage:")
    subprocess.run([
        "pytest", __file__,
        "--cov=filetool.filetool",
        "--cov-report=term-missing",
        "-v"
    ])
