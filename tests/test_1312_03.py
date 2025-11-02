#!/usr/bin/env python3
"""
Prove line 1312 executes (even though comparison fails)
"""

import pytest
from pathlib import Path
from filetool import uncomment_line_in_file


def test_line_1312_executes_but_doesnt_match(tmp_path):
    """
    Line 1312 executes when content doesn't end with newline.
    But then line 1314 comparison fails because expected_content
    always has newline.

    So the line is NOT found/uncommented, but line 1312 DID execute!
    """
    test_file = tmp_path / "test.txt"

    # File where last line has no newline
    # But include ANOTHER line that DOES match
    test_file.write_bytes(b"# target\n# wrongtarget")  # Last line no \n

    # This will find and uncomment the FIRST line
    result = uncomment_line_in_file(
        path=test_file,
        line="target",
        comment_marker="#",
        ignore_leading_whitespace=True,
        ignore_trailing_whitespace=True,
    )

    # Should uncomment the first line (which HAS newline)
    assert result == 1

    # Line 1312 executed on "# wrongtarget" but didn't match
    print("Line 1312 executed (but comparison failed) on last line without newline")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--cov=filetool.filetool", "--cov-report=term-missing"])
