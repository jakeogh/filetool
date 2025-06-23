import pytest
from pathlib import Path
from filetool import append_bytes_to_file

def test_append_bytes_to_file_non_bytes_payload():
    with pytest.raises(TypeError, match=r"bytes_payload must be of type <class 'bytes'>, got float"):
        append_bytes_to_file(
            bytes_payload=1.234,
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=True,
            make_parents=False,
        )
