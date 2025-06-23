import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_full_valid_dedup():
    append_bytes_to_file(
        bytes_payload=b"abc\n",
        path=Path("/tmp/dummy"),
        unique_bytes=True,
        unlink_first=False,
        create_if_missing=True,
        make_parents=False,
        line_ending=b"\n",
        comment_marker=b"#",
        ignore_leading_whitespace=False,
        ignore_trailing_whitespace=False,
    )
