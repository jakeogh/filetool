import pytest
from pathlib import Path
from filetool import ensure_bytes_present  # Adjust import path as needed


def make_kwargs(**overrides):
    """Create a minimal valid argument set, overridden as needed."""
    base = dict(
        path=Path("/tmp/example.txt"),
        bytes_payload=b"line\n",
        unique_bytes=False,
        create_if_missing=False,
        make_parents=False,
        line_ending=None,
        comment_marker=None,
        ignore_leading_whitespace=False,
        ignore_trailing_whitespace=False,
    )
    base.update(overrides)
    return base


def test_bytes_payload_not_empty():
    with pytest.raises(ValueError, match="bytes_payload must not be empty"):
        ensure_bytes_present(**make_kwargs(bytes_payload=b""))


def test_line_ending_requires_unique_bytes():
    with pytest.raises(ValueError, match="line_ending requires unique_bytes=True"):
        ensure_bytes_present(**make_kwargs(line_ending=b"\n", unique_bytes=False))


def test_unique_bytes_requires_line_ending():
    with pytest.raises(ValueError, match="unique_bytes=True requires line_ending"):
        ensure_bytes_present(**make_kwargs(unique_bytes=True, line_ending=None))


def test_line_ending_not_empty_when_unique_bytes():
    with pytest.raises(
        ValueError, match="unique_bytes=True requires line_ending to be non-empty"
    ):
        ensure_bytes_present(**make_kwargs(unique_bytes=True, line_ending=b""))


def test_make_parents_requires_create_if_missing():
    with pytest.raises(
        ValueError, match="make_parents=True requires create_if_missing=True"
    ):
        ensure_bytes_present(**make_kwargs(make_parents=True, create_if_missing=False))


def test_comment_marker_must_be_bytes_or_none():
    with pytest.raises(TypeError,  match=r"comment_marker must be of type .*bytes.*NoneType.*"):
        ensure_bytes_present(
            **make_kwargs(
                comment_marker="not_bytes", unique_bytes=True, line_ending=b"\n"
            )
        )


def test_comment_marker_not_empty_if_set():
    with pytest.raises(
        ValueError, match=r"comment_marker must not be empty if set"
    ):
        ensure_bytes_present(
            **make_kwargs(comment_marker=b"", unique_bytes=True, line_ending=b"\n")
        )


def test_comment_marker_not_equal_to_line_ending():
    with pytest.raises(ValueError, match="comment_marker can not match delim"):
        ensure_bytes_present(
            **make_kwargs(comment_marker=b"#", line_ending=b"#", unique_bytes=True)
        )


def test_comment_marker_not_contain_line_ending():
    with pytest.raises(
        ValueError, match="delim must not be contained in comment_marker"
    ):
        ensure_bytes_present(
            **make_kwargs(comment_marker=b"##", line_ending=b"#", unique_bytes=True, create_if_missing=True,)
        )


def test_ignore_leading_requires_unique_bytes():
    with pytest.raises(
        ValueError, match=r"ignore_leading_whitespace=True requires unique_bytes=True"
    ):
        ensure_bytes_present(**make_kwargs(ignore_leading_whitespace=True))


def test_ignore_trailing_requires_unique_bytes():
    with pytest.raises(
        ValueError, match=r"ignore_trailing_whitespace=True requires unique_bytes=True"
    ):
        ensure_bytes_present(**make_kwargs(ignore_trailing_whitespace=True))
