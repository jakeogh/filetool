import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_minimal_valid():
    append_bytes_to_file(
        bytes_payload=b"abc",
        path=Path("/tmp/dummy"),
        unique_bytes=False,
        unlink_first=False,
        create_if_missing=True,
        make_parents=False,
    )
