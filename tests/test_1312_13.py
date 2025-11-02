#!/usr/bin/env python3
"""
Can we pass a line that's just spaces?
"""

from pathlib import Path
from filetool import uncomment_line_in_file


def test_whitespace_line():
    """Try a line that's just spaces."""
    test_file = Path("/tmp/t.txt")
    test_file.write_bytes(b"#   \n")

    try:
        result = uncomment_line_in_file(
            path=test_file,
            line=" ",  # Just a space!
            comment_marker="#",
            ignore_leading_whitespace=True,
            ignore_trailing_whitespace=True,
        )
        print(f"Success! Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_whitespace_line()
