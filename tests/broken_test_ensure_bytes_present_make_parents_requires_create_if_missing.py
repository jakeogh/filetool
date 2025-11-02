from pathlib import Path

import pytest
from filetool.filetool import _ensure_bytes_present


def test__ensure_bytes_present_make_parents_requires_create_if_missing(tmp_path: Path):
    """
    Test that _ensure_bytes_present raises ValueError if make_parents=True
    and create_if_missing=False, which is a defined conflict.
    """
    path = tmp_path / "missing_dir" / "file.txt"

    with pytest.raises(
        ValueError, match="make_parents=True requires create_if_missing=True"
    ):
        _ensure_bytes_present(
            path=path,
            bytes_payload=b"hello\n",
            unique_bytes=False,
            create_if_missing=False,
            make_parents=True,
            line_ending=None,
            comment_marker=None,
            ignore_leading_whitespace=False,
            ignore_trailing_whitespace=False,
        )
