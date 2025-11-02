from pathlib import Path

import pytest
from filetool import _append_bytes_to_file


def test__append_bytes_to_file_empty_bytes_payload():
    with pytest.raises(ValueError, match="bytes_payload must not be empty"):
        _append_bytes_to_file(
            bytes_payload=b"",
            path=Path("/tmp/dummy"),
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=True,
            make_parents=False,
        )
