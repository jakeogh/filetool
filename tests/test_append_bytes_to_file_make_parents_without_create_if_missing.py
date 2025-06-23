import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_make_parents_without_create_if_missing():
    with pytest.raises(ValueError, match=r"make_parents=True requires create_if_missing=True"):
        append_bytes_to_file(
            bytes_payload=b"test\n",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=False,  # Invalid: make_parents requires this to be True
            make_parents=True,
        )
