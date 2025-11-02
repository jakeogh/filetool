from pathlib import Path

import pytest
from filetool import _append_bytes_to_file


def test__append_bytes_to_file_comment_marker_none_without_unique_bytes():
    # This should not raise
    _append_bytes_to_file(
        bytes_payload=b"test\n",
        path=Path("/tmp/dummy"),
        unlink_first=False,
        unique_bytes=False,  # comment_marker should be ignored
        comment_marker=None,  # Explicitly set to None (valid)
        create_if_missing=True,
        make_parents=False,
    )
