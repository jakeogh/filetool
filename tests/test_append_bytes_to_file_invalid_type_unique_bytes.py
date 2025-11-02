from pathlib import Path

import pytest
from filetool import _append_bytes_to_file


def test__append_bytes_to_file_invalid_type_unique_bytes():
    with pytest.raises(TypeError, match=r"unique_bytes must be of type <class 'bool'>"):
        _append_bytes_to_file(
            bytes_payload=b"abc",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes="yes",  # Not bool
            create_if_missing=True,
            make_parents=False,
        )
