import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_unlink_first_without_unique_bytes():
    with pytest.raises(ValueError, match=r"unlink_first=True requires unique_bytes=True"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=True,           # Invalid: requires unique_bytes=True
            unique_bytes=False,
            create_if_missing=True,
            make_parents=False,
        )
