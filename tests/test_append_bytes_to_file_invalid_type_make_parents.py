from pathlib import Path

import pytest

from filetool import _append_bytes_to_file


def test__append_bytes_to_file_invalid_type_make_parents():
    with pytest.raises(TypeError, match=r"make_parents must be of type <class 'bool'>"):
        _append_bytes_to_file(
            bytes_payload=b"abc",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=True,
            make_parents="true",  # Not bool
        )
