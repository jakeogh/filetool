#!/usr/bin/env python3
"""
HIT LINE 1312 - Uncomment a whitespace-only line!
"""

from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_uncomment_whitespace_line():
    """
    To hit line 1312, we need to uncomment a line that's "# \n"
    So we search for "" (empty line)!
    """
    test_file = Path("/tmp/final.txt")
    test_file.write_bytes(b"#  \n")  # Comment + spaces + newline

    try:
        # Try to uncomment an "empty" line (just whitespace)
        result = uncomment_line_in_file(
            path=test_file,
            line="",  # Empty line!
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )

        print(f"Result: {result}")

    except ValueError as e:
        print(f"Error: {e}")
        # Line validation will fail because line="" is invalid
    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_line_1312_uncomment_whitespace_line()
