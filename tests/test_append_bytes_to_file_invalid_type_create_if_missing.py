import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_invalid_type_create_if_missing():
    with pytest.raises(TypeError, match=r"create_if_missing must be of type <class 'bool'>"):
        append_bytes_to_file(
            bytes_payload=b"abc",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            create_if_missing="yes",  # Not bool
            make_parents=False,
        )
