from pathlib import Path

import pytest
from filetool import _append_bytes_to_file


def test__append_bytes_to_file_non_bytes_payload():
    with pytest.raises(
        TypeError, match=r"bytes_payload must be of type <class 'bytes'>, got float"
    ):
        _append_bytes_to_file(
            bytes_payload=1.234,
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=True,
            make_parents=False,
        )
