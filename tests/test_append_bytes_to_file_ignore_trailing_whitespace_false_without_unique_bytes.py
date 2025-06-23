import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_ignore_trailing_whitespace_false_without_unique_bytes():
    append_bytes_to_file(
        bytes_payload=b"abc",
        path=Path("/tmp/dummy"),
        unique_bytes=False,
        line_ending=None,
        ignore_trailing_whitespace=False,
        create_if_missing=True,
        make_parents=False,
        unlink_first=False,
    )