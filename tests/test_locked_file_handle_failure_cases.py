import gc
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from filetool import locked_file_handle

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
    "which_fn,expect_close_exception",
    [
        (locked_file_handle_orig, True),
        (locked_file_handle, False),
    ],
)
def test_fh_close_failure_does_not_release_lock_param(
    temp_file, capsys, which_fn, expect_close_exception
):
    real_open = open
    recorded_fh = {}

    def wrapped_open(*args, **kwargs):
        fh = real_open(*args, **kwargs)
        mocked_close = mock.Mock(side_effect=OSError("close failed"))
        fh.close = mocked_close
        recorded_fh["handle"] = fh
        return fh

    with mock.patch("builtins.open", wrapped_open):
        if expect_close_exception:
            with pytest.raises(OSError, match="close failed"):
                with which_fn(path=temp_file, mode="rb+", blocking=True, create=True) as fh:
                    fh.write(b"x")
        else:
            with which_fn(path=temp_file, mode="rb+", blocking=True, create=True) as fh:
                fh.write(b"x")

    recorded_fh["handle"].close.assert_called_once()

    if not expect_close_exception:
        out = capsys.readouterr()
        assert "Warning: error during final cleanup of file" in out.err
        assert "close failed" in out.err

    with which_fn(path=temp_file, mode="rb+", blocking=True, create=False) as fh2:
        fh2.write(b"y")

    if "handle" in recorded_fh:
        with open(temp_file, "rb") as f:
            recorded_fh["handle"].close = f.close
    gc.collect()

    if 'fh' in locals():
        del fh
    gc.collect()


def test_unlock_fails_but_close_succeeds(temp_file):
    with mock.patch(
        "fcntl.flock", side_effect=[None, OSError("unlock failed")]
    ) as mock_flock, mock.patch("builtins.print") as mock_print:
        with locked_file_handle(
            path=temp_file, mode="rb+", blocking=True, create=True
        ) as fh:
            fh.write(b"test")

        printed = any(
            "Warning: failed to unlock file" in str(call.args[0])
            for call in mock_print.call_args_list
        )
        assert printed

    if "handle" in locals():
        with open(temp_file, "rb") as f:
            handle = f
            handle.close = f.close
    gc.collect()

    if 'fh' in locals():
        del fh
    gc.collect()


@pytest.mark.parametrize(
    "which_fn, expect_exception, expect_unlock_warning, expect_close_warning",
    [
        (locked_file_handle_orig, True, True, False),
        (locked_file_handle, False, True, True),
    ],
)
def test_unlock_and_close_both_fail_param(
    temp_file,
    capsys,
    which_fn,
    expect_exception,
    expect_unlock_warning,
    expect_close_warning,
):
    real_open = open
    recorded_fh = {}

    def wrapped_open(*args, **kwargs):
        fh = real_open(*args, **kwargs)
        mocked_close = mock.Mock(side_effect=OSError("close failed"))
        fh.close = mocked_close
        recorded_fh["handle"] = fh
        return fh

    flock_side_effect = [None, OSError("unlock failed")]

    with mock.patch("builtins.open", wrapped_open), mock.patch(
        "fcntl.flock", side_effect=flock_side_effect
    ):
        if expect_exception:
            with pytest.raises(OSError, match="close failed"):
                with which_fn(path=temp_file, mode="rb+", blocking=True, create=True) as fh:
                    fh.write(b"payload")
        else:
            with which_fn(path=temp_file, mode="rb+", blocking=True, create=True) as fh:
                fh.write(b"payload")

    recorded_fh["handle"].close.assert_called_once()

    out = capsys.readouterr().err
    if expect_unlock_warning:
        assert "Warning: failed to unlock file" in out
    else:
        assert "Warning: failed to unlock file" not in out

    if expect_close_warning:
        assert "Warning: error during final cleanup of file" in out
        assert "close failed" in out
    else:
        assert "Warning: error during final cleanup of file" not in out

    if "handle" in recorded_fh:
        with open(temp_file, "rb") as f:
            recorded_fh["handle"].close = f.close
    gc.collect()

    if 'fh' in locals():
        del fh
    gc.collect()
