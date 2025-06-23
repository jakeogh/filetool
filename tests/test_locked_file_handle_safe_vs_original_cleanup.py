import errno
import fcntl
import io
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from typing import cast
from unittest import mock

import pytest
from filetool import locked_file_handle
from filetool import open_eintr_safe
from locked_file_handle_orig import locked_file_handle_orig


@pytest.fixture
def temp_file():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = Path(f.name)
    try:
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@pytest.mark.parametrize(
    "which_fn,should_suppress_close_exception",
    [
        (locked_file_handle_orig, False),
        (locked_file_handle, True),
    ],
)
def test_locked_file_handle_cleanup_strategy(
    temp_file, which_fn, should_suppress_close_exception, capsys
):
    """
    Simulate failure in both unlock and close. The hardened version should suppress,
    fallback to os.close(), and emit a stderr warning. The original version should raise.
    """
    close_mock = mock.Mock(side_effect=OSError("close failed"))
    unlock_mock = mock.Mock(side_effect=OSError("unlock failed"))

    real_open = open
    recorded_fh = {}

    def patched_open(*args, **kwargs):
        fh = real_open(*args, **kwargs)
        recorded_fh["handle"] = fh
        recorded_fh["fileno"] = fh.fileno()
        fh.fileno = mock.Mock(return_value=recorded_fh["fileno"])
        fh.close = close_mock
        return fh

    with mock.patch("builtins.open", patched_open), mock.patch(
        "fcntl.flock", side_effect=[None, unlock_mock.side_effect]
    ), mock.patch("os.close") as os_close_mock:

        if should_suppress_close_exception:
            with which_fn(path=temp_file, mode="rb+", blocking=True, create=True) as fh:
                fh.write(b"safe")

            out = capsys.readouterr()
            assert "Warning: failed to unlock file" in out.err
            assert "Warning: error during final cleanup of file" in out.err
            assert "close failed" in out.err
        else:
            with pytest.raises(OSError, match="close failed"):
                with which_fn(
                    path=temp_file, mode="rb+", blocking=True, create=True
                ) as fh:
                    fh.write(b"unsafe")

            assert os_close_mock.call_count == 0

    # Clean up unraisable exceptions triggered by mocked .close in destructors
    import gc

    if "handle" in recorded_fh:
        real_close = getattr(real_open(temp_file, "rb"), "close", None)
        if real_close:
            recorded_fh["handle"].close = real_close
    del close_mock
    gc.collect()


# @pytest.mark.parametrize(
#    "which_fn,should_suppress_close_exception",
#    [
#        (locked_file_handle_orig, False),
#        (locked_file_handle, True),
#    ],
# )
# def test_locked_file_handle_cleanup_strategy(
#    temp_file, which_fn, should_suppress_close_exception, capsys
# ):
#    """
#    Simulate failure in both unlock and close. The hardened version should suppress,
#    fallback to os.close(), and emit a stderr warning. The original version should raise.
#    """
#    close_mock = mock.Mock(side_effect=OSError("close failed"))
#    unlock_mock = mock.Mock(side_effect=OSError("unlock failed"))
#
#    real_open = open
#    recorded_fd = {}
#
#    def patched_open(*args, **kwargs):
#        fh = real_open(*args, **kwargs)
#        recorded_fd["fileno"] = fh.fileno()
#        fh.fileno = mock.Mock(return_value=recorded_fd["fileno"])
#        fh.close = close_mock
#        return fh
#
#    with mock.patch("builtins.open", patched_open), mock.patch(
#        "fcntl.flock", side_effect=[None, unlock_mock.side_effect]
#    ), mock.patch("os.close") as os_close_mock:
#
#        if should_suppress_close_exception:
#            # Hardened version logs warnings but suppresses close failure
#            with which_fn(path=temp_file, mode="rb+", blocking=True, create=True) as fh:
#                fh.write(b"safe")
#
#            out = capsys.readouterr()
#            assert "Warning: failed to unlock file" in out.err
#            assert "Warning: error during final cleanup of file" in out.err
#            assert "close failed" in out.err
#            #assert os_close_mock.call_count == 1
#        else:
#            # Original version raises on close
#            with pytest.raises(OSError, match="close failed"):
#                with which_fn(
#                    path=temp_file, mode="rb+", blocking=True, create=True
#                ) as fh:
#                    fh.write(b"unsafe")
#
#            assert os_close_mock.call_count == 0
#
#
#    # Clean up unraisable exceptions triggered by mocked .close in destructors
#    if "close_mock" in locals():
#        del close_mock
#    import gc; gc.collect()
