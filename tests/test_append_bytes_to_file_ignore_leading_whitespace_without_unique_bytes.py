import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_ignore_leading_whitespace_without_unique_bytes():
    with pytest.raises(ValueError, match=r"ignore_leading_whitespace=True requires unique_bytes=True"):
        append_bytes_to_file(
            bytes_payload=b"  test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,                   # Invalid: required if ignore_leading_whitespace is True
            ignore_leading_whitespace=True,       # Set without unique_bytes=True
            create_if_missing=True,
            make_parents=False,
        )
