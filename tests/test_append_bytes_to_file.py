# import threading
# import time
import gc
import multiprocessing
import os
import random
import stat
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from filetool import append_bytes_to_file
from filetool import (
    cli,
)  # Make sure 'filetool' is importable in your pytest environment

# from filetool import splitlines_bytes_safe
from hypothesis import HealthCheck
from hypothesis import Phase
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

import io
import pytest
from filetool import splitlines_bytes
import io
import psutil
import time
import pytest
from filetool import splitlines_bytes

try:
    _ = psutil.Process().memory_info()
except Exception as e:
    warnings.warn(f"psutil.Process().memory_info() not accessible: {type(e).__name__}: {e}")


def test_append_bytes_to_file_basic_cli(tmp_path: Path):
    test_file = tmp_path / "testfile.txt"
    test_file.write_text("existing\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append",
            "new line",
            "--path", str(test_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert test_file.read_text() == "existing\nnew line\n"
    assert f"Wrote 9 bytes to {test_file}" in result.output



def test_append_bytes_to_file_basic_cli(tmp_path: Path):
    test_file = tmp_path / "testfile.txt"
    test_file.write_text("existing\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append",
            "new line",
            "--path",
            str(test_file),
        ],
    )

    assert result.exit_code == 0
    assert test_file.read_text() == "existing\nnew line\n"
    assert f"Wrote 9 bytes to {test_file}" in result.output


def test_append_bytes_to_file_basic_cli(tmp_path: Path):
    test_file = tmp_path / "testfile.txt"
    test_file.write_text("existing\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append",
            "new line",
            "--path",
            str(test_file),
            "--create",
        ],
    )

    assert result.exit_code == 0
    assert test_file.read_text() == "existing\nnew line\n"
    assert f"Wrote 9 bytes to {test_file}" in result.output


@pytest.mark.parametrize(
    "create_flag, file_exists, should_succeed",
    [
        (False, True, True),  # file exists, no --create
        (True, True, True),  # file exists, with --create
        (False, False, False),  # file missing, no --create → should fail
        (True, False, True),  # file missing, with --create → should succeed
    ],
)
def test_append_bytes_to_file_basic_cli_parametrize(
    tmp_path: Path, create_flag: bool, file_exists: bool, should_succeed: bool
):
    test_file = tmp_path / "testfile.txt"
    if file_exists:
        test_file.write_text("existing\n")

    args = [
        "append",
        "new line",
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    if should_succeed:
        assert result.exit_code == 0
        contents = test_file.read_text()
        expected_prefix = "existing\n" if file_exists else ""
        assert contents == expected_prefix + "new line\n"
        assert f"Wrote 9 bytes to {test_file}" in result.output
    else:
        assert result.exit_code != 0
        assert "No such file or directory" in result.output or "Error" in result.output


@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("create_flag", [False, True])
def test_append_bytes_to_file_cli_two_flags(
    tmp_path: Path, create_flag: bool, make_parents_flag: bool, file_exists: bool
):
    subdir = tmp_path / "missing_dir"
    test_file = subdir / "testfile.txt"

    if file_exists:
        subdir.mkdir(parents=True)
        test_file.write_text("existing\n")

    args = [
        "append",
        "new line",
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    invalid_combo = not create_flag and make_parents_flag
    should_succeed = (
        file_exists or (create_flag and make_parents_flag)
    ) and not invalid_combo

    #print("ARGS:", args)
    #print("OUTPUT:", result.output)

    if invalid_combo:
        assert result.exit_code != 0
        assert "create_if_missing=False requires make_parents=False" in result.output

    elif should_succeed:
        assert result.exit_code == 0, result.output
        contents = test_file.read_text()
        expected_prefix = "existing\n" if file_exists else ""
        assert contents == expected_prefix + "new line\n"
        assert f"Wrote 9 bytes to {test_file}" in result.output

    else:
        assert result.exit_code != 0
        assert (
            not test_file.exists()
            or "No such file" in result.output
            or "Error" in result.output
        )


from pathlib import Path

import pytest
from click.testing import CliRunner
from filetool import cli


@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("create_flag", [False, True])
@pytest.mark.parametrize("unlink_first_flag", [False, True])
def test_append_bytes_to_file_cli_three_flags(
    tmp_path: Path,
    create_flag: bool,
    make_parents_flag: bool,
    unlink_first_flag: bool,
    file_exists: bool,
):
    subdir = tmp_path / "missing_dir"
    test_file = subdir / "testfile.txt"

    if file_exists:
        subdir.mkdir(parents=True)
        test_file.write_text("existing\n")

    args = [
        "append",
        "new line",
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    print("ARGS:", args)
    print("OUTPUT:", result.output)

    # === Constraint 1 (highest priority): unlink_first=True requires unique_bytes=True ===
    if unlink_first_flag:
        assert result.exit_code != 0
        assert "unlink_first=True requires unique_bytes=True" in result.output
        return

    # === Constraint 2: create_if_missing=False requires make_parents=False ===
    if not create_flag and make_parents_flag:
        assert result.exit_code != 0
        assert "create_if_missing=False requires make_parents=False" in result.output
        return

    # === Success case ===
    should_succeed = file_exists or (create_flag and make_parents_flag)

    if should_succeed:
        assert result.exit_code == 0, result.output
        expected_prefix = "existing\n" if file_exists else ""
        assert test_file.read_text() == expected_prefix + "new line\n"
        assert f"Wrote 9 bytes to {test_file}" in result.output
    else:
        assert result.exit_code != 0
        assert "Error" in result.output or "No such file" in result.output


@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("create_flag", [False, True])
@pytest.mark.parametrize("unlink_first_flag", [False, True])
@pytest.mark.parametrize("dry_run_flag", [False, True])
def test_append_bytes_to_file_cli_four_flags(
    tmp_path: Path,
    create_flag: bool,
    make_parents_flag: bool,
    unlink_first_flag: bool,
    dry_run_flag: bool,
    file_exists: bool,
):
    subdir = tmp_path / "missing_dir"
    test_file = subdir / "testfile.txt"

    if file_exists:
        subdir.mkdir(parents=True)
        test_file.write_text("existing\n")

    args = [
        "append",
        "new line",
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")
    if dry_run_flag:
        args.append("--dry-run")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    print("ARGS:", args)
    print("OUTPUT:", result.output)

    # Constraint 1: unlink_first requires unique_bytes
    if unlink_first_flag:
        assert result.exit_code != 0
        assert "unlink_first=True requires unique_bytes=True" in result.output
        return

    # Constraint 2: create_if_missing=False with make_parents=True
    if not create_flag and make_parents_flag:
        assert result.exit_code != 0
        assert "create_if_missing=False requires make_parents=False" in result.output
        return

    should_succeed = file_exists or (create_flag and make_parents_flag)

    if dry_run_flag:
        assert result.exit_code == 0, result.output
        assert "[dry-run]" in result.output
        assert f"Would write: b'new line\\n' to {test_file}" in result.output
        if file_exists:
            assert test_file.read_text() == "existing\n"
        else:
            assert not test_file.exists()
    elif should_succeed:
        assert result.exit_code == 0, result.output
        expected_prefix = "existing\n" if file_exists else ""
        assert test_file.read_text() == expected_prefix + "new line\n"
        assert f"Wrote 9 bytes to {test_file}" in result.output
    else:
        assert result.exit_code != 0
        assert "Error" in result.output or "No such file" in result.output


@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("create_flag", [False, True])
@pytest.mark.parametrize("unlink_first_flag", [False, True])
@pytest.mark.parametrize("dry_run_flag", [False, True])
@pytest.mark.parametrize("hex_input_flag", [False, True])
def test_append_bytes_to_file_cli_five_flags(
    tmp_path: Path,
    create_flag: bool,
    make_parents_flag: bool,
    unlink_first_flag: bool,
    dry_run_flag: bool,
    hex_input_flag: bool,
    file_exists: bool,
):
    subdir = tmp_path / "missing_dir"
    test_file = subdir / "testfile.txt"

    hex_data = "64656661756c74203d20313030"  # "default = 100"
    plain_data = "default = 100"
    input_text = hex_data if hex_input_flag else plain_data

    if file_exists:
        subdir.mkdir(parents=True)
        test_file.write_text("existing\n")

    args = [
        "append",
        input_text,
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")
    if dry_run_flag:
        args.append("--dry-run")
    if hex_input_flag:
        args.append("--hex-input")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    print("ARGS:", args)
    print("OUTPUT:", result.output)

    # Constraint 1: unlink_first requires unique_bytes
    if unlink_first_flag:
        assert result.exit_code != 0
        assert "unlink_first=True requires unique_bytes=True" in result.output
        return

    # Constraint 2: create_if_missing=False with make_parents=True
    if not create_flag and make_parents_flag:
        assert result.exit_code != 0
        assert "create_if_missing=False requires make_parents=False" in result.output
        return

    should_succeed = file_exists or (create_flag and make_parents_flag)
    expected_line = "default = 100\n"

    if dry_run_flag:
        assert result.exit_code == 0, result.output
        assert "[dry-run]" in result.output
        # assert f"Would write: b'{expected_line.encode()}' to {test_file}" in result.output
        assert (
            f"Would write: {repr(expected_line.encode())} to {test_file}"
            in result.output
        )

        if file_exists:
            assert test_file.read_text() == "existing\n"
        else:
            assert not test_file.exists()
    elif should_succeed:
        assert result.exit_code == 0, result.output
        expected_prefix = "existing\n" if file_exists else ""
        assert test_file.read_text() == expected_prefix + expected_line
        assert f"Wrote {len(expected_line)} bytes to {test_file}" in result.output
    else:
        assert result.exit_code != 0
        assert "Error" in result.output or "No such file" in result.output


@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("create_flag", [False, True])
@pytest.mark.parametrize("unlink_first_flag", [False, True])
@pytest.mark.parametrize("dry_run_flag", [False, True])
@pytest.mark.parametrize("hex_input_flag", [False, True])
@pytest.mark.parametrize("no_append_newline_flag", [False, True])
def test_append_bytes_to_file_cli_six_flags(
    tmp_path: Path,
    create_flag: bool,
    make_parents_flag: bool,
    unlink_first_flag: bool,
    dry_run_flag: bool,
    hex_input_flag: bool,
    no_append_newline_flag: bool,
    file_exists: bool,
):
    subdir = tmp_path / "missing_dir"
    test_file = subdir / "testfile.txt"

    hex_data = "64656661756c74203d20313030"  # "default = 100"
    plain_data = "default = 100"
    input_text = hex_data if hex_input_flag else plain_data

    if file_exists:
        subdir.mkdir(parents=True)
        test_file.write_text("existing\n")

    args = [
        "append",
        input_text,
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")
    if dry_run_flag:
        args.append("--dry-run")
    if hex_input_flag:
        args.append("--hex-input")
    if no_append_newline_flag:
        args.append("--do-not-append-newline")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    print("ARGS:", args)
    print("OUTPUT:", result.output)

    # Constraint 1: unlink_first requires unique_bytes
    if unlink_first_flag:
        assert result.exit_code != 0
        assert "unlink_first=True requires unique_bytes=True" in result.output
        return

    # Constraint 2: create_if_missing=False with make_parents=True
    if not create_flag and make_parents_flag:
        assert result.exit_code != 0
        assert "create_if_missing=False requires make_parents=False" in result.output
        return

    should_succeed = file_exists or (create_flag and make_parents_flag)

    # expected_bytes = (plain_data if not hex_input_flag else bytes.fromhex(hex_data))
    # if not no_append_newline_flag:
    #    expected_bytes += b"\n"

    if hex_input_flag:
        expected_bytes = bytes.fromhex(hex_data)
    else:
        expected_bytes = plain_data.encode()

    if not no_append_newline_flag:
        expected_bytes += b"\n"

    if dry_run_flag:
        assert result.exit_code == 0, result.output
        assert "[dry-run]" in result.output
        assert f"Would write: {repr(expected_bytes)} to {test_file}" in result.output
        if file_exists:
            assert test_file.read_text() == "existing\n"
        else:
            assert not test_file.exists()
    elif should_succeed:
        assert result.exit_code == 0, result.output
        expected_prefix = "existing\n" if file_exists else ""
        expected_content = expected_prefix.encode() + expected_bytes
        assert test_file.read_bytes() == expected_content
        assert f"Wrote {len(expected_bytes)} bytes to {test_file}" in result.output
    else:
        assert result.exit_code != 0
        assert "Error" in result.output or "No such file" in result.output


@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("create_flag", [False, True])
@pytest.mark.parametrize("unlink_first_flag", [False, True])
@pytest.mark.parametrize("dry_run_flag", [False, True])
@pytest.mark.parametrize("hex_input_flag", [False, True])
@pytest.mark.parametrize("do_not_append_newline_flag", [False, True])
@pytest.mark.parametrize("unique_flag", [False, True])
def test_append_bytes_to_file_cli_seven_flags(
    tmp_path: Path,
    create_flag: bool,
    make_parents_flag: bool,
    unlink_first_flag: bool,
    dry_run_flag: bool,
    hex_input_flag: bool,
    do_not_append_newline_flag: bool,
    unique_flag: bool,
    file_exists: bool,
):
    subdir = tmp_path / "missing_dir"
    test_file = subdir / "testfile.txt"

    hex_data = "64656661756c74203d20313030"  # "default = 100"
    plain_data = "default = 100"
    input_text = hex_data if hex_input_flag else plain_data

    if file_exists:
        subdir.mkdir(parents=True)
        existing = "existing\n" if not hex_input_flag else "6578697374696e670a"
        test_file.write_text(
            existing
            if not hex_input_flag
            else bytes.fromhex(existing).decode("utf-8", "ignore")
        )

    args = [
        "append",
        input_text,
        "--path",
        str(test_file),
    ]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")
    if dry_run_flag:
        args.append("--dry-run")
    if hex_input_flag:
        args.append("--hex-input")
    if do_not_append_newline_flag:
        args.append("--do-not-append-newline")
    if unique_flag:
        args.append("--unique")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    print("ARGS:", args)
    print("OUTPUT:", result.output)

    # Constraint: --unlink-first requires --unique
    if unlink_first_flag and not unique_flag:
        assert result.exit_code != 0
        assert "unlink_first=True requires unique_bytes=True" in result.output
        return

    # Constraint 2: create_if_missing=False with make_parents=True
    if not create_flag and make_parents_flag:
        assert result.exit_code != 0
        assert "create_if_missing=False requires make_parents=False" in result.output
        return

    should_succeed = file_exists or (create_flag and make_parents_flag)

    expected_bytes = bytes.fromhex(hex_data) if hex_input_flag else plain_data.encode()
    if not do_not_append_newline_flag:
        expected_bytes += b"\n"

    if dry_run_flag:
        assert result.exit_code == 0, result.output
        assert "[dry-run]" in result.output
        assert f"Would write: {repr(expected_bytes)} to {test_file}" in result.output
        if file_exists:
            old_contents = test_file.read_text()
            assert "existing" in old_contents
        else:
            assert not test_file.exists()
    elif should_succeed:
        assert result.exit_code == 0, result.output
        final_bytes = test_file.read_bytes()
        if file_exists and not unlink_first_flag and not unique_flag:
            assert final_bytes.endswith(expected_bytes)
        elif file_exists and unique_flag:
            assert final_bytes.count(expected_bytes) == 1
        else:
            assert final_bytes == expected_bytes
        assert f"Wrote {len(expected_bytes)} bytes to {test_file}" in result.output
    else:
        assert result.exit_code != 0
        assert "Error" in result.output or "No such file" in result.output


def test_append_bytes_to_file_cli_hex_input_bad():
    """Verify --hex-input rejects invalid hex strings with proper error."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "append",
            "this_is_not_hex",
            "--path",
            "/tmp/should_not_be_created.txt",
            "--hex-input",
            "--create",
        ],
    )

    print("OUTPUT:", result.output)
    assert result.exit_code != 0
    assert "non-hexadecimal number found" in result.output or "Error" in result.output




@pytest.mark.parametrize("create_flag", [False, True])
@pytest.mark.parametrize("make_parents_flag", [False, True])
@pytest.mark.parametrize("unlink_first_flag", [False, True])
@pytest.mark.parametrize("dry_run_flag", [False, True])
def test_permission_denied_cli(
    tmp_path, create_flag, make_parents_flag, unlink_first_flag, dry_run_flag
):
    test_file = tmp_path / "readonly.txt"
    test_file.write_text("readonly\n")
    os.chmod(test_file, 0o444)  # read-only

    args = ["append", "some data", "--path", str(test_file)]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")
    if dry_run_flag:
        args.append("--dry-run")

    result = CliRunner().invoke(cli, args)

    # === Constraint: unlink_first requires unique
    unlink_constraint = unlink_first_flag and "--unique" not in args
    # === Constraint: create_if_missing=False with make_parents=True
    make_parent_constraint = not create_flag and make_parents_flag

    if unlink_constraint or make_parent_constraint:
        assert result.exit_code != 0
        assert (
            "unlink_first=True requires unique_bytes=True" in result.output
            or "create_if_missing=False requires make_parents=False" in result.output
        )
        return

    # === Now check permission handling
    if dry_run_flag:
        assert result.exit_code == 0, result.output
    else:
        assert result.exit_code != 0
        assert (
            "Permission" in result.output
            or "denied" in result.output
            or "Error" in result.output
        )


def test_path_is_directoryi_cli(tmp_path):
    result = CliRunner().invoke(cli, ["data", "--path", str(tmp_path)])
    assert result.exit_code != 0
    assert "Is a directory" in result.output or "Error" in result.output


@pytest.mark.parametrize("do_not_append_newline", [False, True])
def test_binary_unique_bytes_append(tmp_path, do_not_append_newline):
    binfile = tmp_path / "binfile"
    # Initial content does NOT contain b'\xff\xfe'
    binfile.write_bytes(b"\xaa\xbb\xcc")

    args = ["append", "fffe", "--path", str(binfile), "--unique", "--hex-input"]
    if do_not_append_newline:
        args.append("--do-not-append-newline")

    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0

    final_bytes = binfile.read_bytes()
    expected_append = b"\xff\xfe" + (b"" if do_not_append_newline else b"\n")
    assert final_bytes.endswith(expected_append)


@pytest.mark.parametrize("do_not_append_newline", [False, True])
def test_binary_unique_bytes_skip_append(tmp_path, do_not_append_newline):
    binfile = tmp_path / "binfile"
    # Write initial content that ALREADY contains the unique check target
    prefix = b"\xff\xfe"
    suffix = b"\xfd"
    newline = b"" if do_not_append_newline else b"\n"
    binfile.write_bytes(prefix + suffix + newline)

    args = ["append", "fffe", "--path", str(binfile), "--unique", "--hex-input"]
    if do_not_append_newline:
        args.append("--do-not-append-newline")

    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0

    final_bytes = binfile.read_bytes()
    # Ensure additional append occurred
    print(final_bytes)
    print(len(final_bytes))
    if newline:
        assert len(final_bytes) == 7
    else:
        assert len(final_bytes) == 5



def test_unique_append_to_empty_file(tmp_path):
    f = tmp_path / "empty"
    f.write_bytes(b"")  # empty
    result = CliRunner().invoke(cli, ["append", "hi", "--path", str(f), "--unique"])
    assert result.exit_code == 0
    assert f.read_bytes() == b"hi\n"


def test_unique_line_exists_multiple_times(tmp_path):
    f = tmp_path / "file"
    f.write_text("dup\nsomething\ndup\n")
    result = CliRunner().invoke(cli, ["append", "dup", "--path", str(f), "--unique"])
    assert result.exit_code == 0
    assert f.read_text().count("dup") == 2


def test_symlink_write(tmp_path):
    target = tmp_path / "realfile"
    target.write_text("")
    symlink = tmp_path / "link"
    symlink.symlink_to(target)

    result = CliRunner().invoke(cli, ["append", "hi", "--path", str(symlink)])
    assert result.exit_code == 0
    assert target.read_text() == "hi\n"


@pytest.mark.parametrize("create_flag", [True])
@pytest.mark.parametrize("make_parents_flag", [True])
@pytest.mark.parametrize("unlink_first_flag", [True])
@pytest.mark.parametrize("unique_flag", [True])
@pytest.mark.parametrize("dry_run_flag", [True])
def test_dry_run_simulation(
    create_flag,
    make_parents_flag,
    unlink_first_flag,
    unique_flag,
    dry_run_flag,
    tmp_path,
):
    file_path = tmp_path / "dir1" / "nested" / "file.conf"

    args = ["append", "config_entry = true", "--path", str(file_path)]
    if create_flag:
        args.append("--create")
    if make_parents_flag:
        args.append("--make-parents")
    if unlink_first_flag:
        args.append("--unlink-first")
    if unique_flag:
        args.append("--unique")
    if dry_run_flag:
        args.append("--dry-run")

    runner = CliRunner()
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    assert "[dry-run]" in result.output
    assert "Would write" in result.output
    assert not file_path.exists()


@pytest.mark.parametrize(
    "bad_hex",
    [
        "0",  # odd length
        "gh",  # invalid hex characters
        "12zz",  # partial valid, partial invalid
        "FFFFF",  # odd length with valid hex
        "xyz123",  # non-hex prefix
        "6869!",  # valid hex with non-hex trailing
        "123\n456",  # newline in input
        " 6869",  # leading space
        "6869 ",  # trailing space
        "\x00\x01",  # non-printable
    ],
)
def test_malformed_hex_input_cli(tmp_path, bad_hex):
    file_path = tmp_path / "output.bin"

    args = ["append", bad_hex, "--path", str(file_path), "--hex-input"]
    result = CliRunner().invoke(cli, args)

    assert result.exit_code != 0
    assert "hex" in result.output.lower() or "Error" in result.output
    assert not file_path.exists()


@pytest.mark.parametrize("dry_run_flag", [False, True])
def test_path_is_directory_permission_denied(tmp_path: Path, dry_run_flag: bool):
    test_file = tmp_path / "dir_as_file"
    test_file.mkdir()  # create a directory in place of the file

    args = ["append", "some data", "--path", str(test_file)]
    if dry_run_flag:
        args.append("--dry-run")

    result = CliRunner().invoke(cli, args)

    if dry_run_flag:
        # In dry-run mode, no filesystem checks are done
        assert result.exit_code == 0
        assert "Would write:" in result.output
    else:
        assert result.exit_code != 0
        assert (
            "Is a directory" in result.output
            or "Permission" in result.output
            or "Error" in result.output
        )


def test_append_empty_line_creates_file_without_flags(tmp_path: Path):
    """This test verifies that writing an empty string to a non-existent file
    without --create or --make-parents should fail."""
    target_file = tmp_path / "nonexistent_dir" / "file.txt"
    assert not target_file.exists()
    args = ["", "--path", str(target_file)]

    result = CliRunner().invoke(cli, args)

    assert result.exit_code != 0, f"Expected failure but got: {result.output}"
    assert (
        "create_if_missing" in result.output
        or "No such file" in result.output
        or "Error" in result.output
    )
    assert not target_file.exists(), "File was unexpectedly created"



def test_empty_input_does_not_write(tmp_path: Path):
    """Empty input ("" as first argument) should not write to the file."""
    target = tmp_path / "file.txt"
    original_bytes = b"ORIGINAL\n"
    target.write_bytes(original_bytes)
    mtime_before = target.stat().st_mtime_ns
    size_before = target.stat().st_size

    result = CliRunner().invoke(cli, ["append", "", "--path", str(target)])

    assert result.exit_code != 0, "Empty input should cause a failure"
    assert (
        "you must specify bytes to add" in result.output
        or "empty" in result.output.lower()
        or "no input" in result.output.lower()
        or "error" in result.output.lower()
    )

    mtime_after = target.stat().st_mtime_ns
    size_after = target.stat().st_size
    final_bytes = target.read_bytes()

    assert mtime_after == mtime_before, "File mtime changed unexpectedly"
    assert size_after == size_before, "File size changed unexpectedly"
    assert final_bytes == original_bytes, "File content changed unexpectedly"


@pytest.mark.parametrize("symlink_type", ["file", "dir", "broken"])
def test_symlink_targets(tmp_path: Path, symlink_type: str):
    target_file = tmp_path / "actual_file.txt"
    target_dir = tmp_path / "actual_dir"
    broken_target = tmp_path / "missing_target"
    link_path = tmp_path / "symlink"

    if symlink_type == "file":
        target_file.write_text("existing\n")
        os.symlink(target_file, link_path)
        result = CliRunner().invoke(
            cli, ["append", "new line", "--path", str(link_path), "--create"]
        )
        print("STDOUT:\n", result.output)
        assert result.exit_code == 0
        assert "Wrote" in result.output

    elif symlink_type == "dir":
        target_dir.mkdir()
        os.symlink(target_dir, link_path)
        result = CliRunner().invoke(
            cli, ["append", "--path", str(link_path), "--create"]
        )
        assert result.exit_code != 0
        assert "Is a directory" in result.output or "Error" in result.output

    elif symlink_type == "broken":
        os.symlink(broken_target, link_path)
        result = CliRunner().invoke(
            cli, ["append", "--path", str(link_path), "--create"]
        )
        assert result.exit_code != 0
        assert "No such file" in result.output or "Error" in result.output


def test_locale_utf8_edge_case(tmp_path: Path):
    target = tmp_path / "file.txt"

    result = CliRunner().invoke(
        cli,
        ["append", "日本語", "--path", str(target), "--create"],
        env={"LC_ALL": "C", "LANG": "C", "PYTHONIOENCODING": "ascii"},
    )

    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").strip() == "日本語"


@pytest.mark.parametrize("cause", ["open", "write"])
def test_io_error_simulation(tmp_path: Path, monkeypatch, cause: str):
    file_path = tmp_path / "target.txt"

    if cause == "open":

        def bad_open(*args, **kwargs):
            raise OSError("simulated open failure")

        monkeypatch.setattr("builtins.open", bad_open)

    elif cause == "write":

        class DummyFile:
            def write(self, *_):
                raise OSError("simulated write failure")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def fileno(self):
                return 1

            def close(self):
                pass

            def seek(self, offset, whence=0):
                return 0

            def flush(self):
                pass

            def tell(self):
                return 0

            def read(self, *a, **kw):
                return b""  # Allow read() for --unique etc.

        def fake_open(*args, **kwargs):
            return DummyFile()

        monkeypatch.setattr("builtins.open", fake_open)

    result = CliRunner().invoke(cli, ["append", "abc", "--path", str(file_path), "--create"])
    assert result.exit_code != 0
    assert "simulated" in result.output.lower() or "error" in result.output.lower()



import pytest
from pathlib import Path
from click.testing import CliRunner
from filetool import cli  # adjust as needed


@pytest.mark.parametrize(
    "cause,unique,unlink_first",
    [
        ("open", False, False),
        ("open", False, True),
        ("open", True, False),
        ("open", True, True),
        ("write", False, False),
        ("write", False, True),
        ("write", True, False),
        ("write", True, True),
    ],
)
def test_io_error_simulation_2(
    tmp_path: Path, monkeypatch, cause: str, unique: bool, unlink_first: bool
):
    file_path = tmp_path / "target.txt"

    if cause == "open":

        def bad_open(*args, **kwargs):
            raise OSError("simulated open failure")

        monkeypatch.setattr("builtins.open", bad_open)

    elif cause == "write":

        class DummyFile:
            def write(self, *_):
                raise OSError("simulated write failure")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def fileno(self):
                return 1

            def close(self):
                pass

            def seek(self, offset, whence=0):
                return 0

            def flush(self):
                pass

            def tell(self):
                return 0

            def read(self, *a, **kw):
                return b""  # for --unique reads

        def fake_open(*args, **kwargs):
            return DummyFile()

        monkeypatch.setattr("builtins.open", fake_open)

    args = ["append", "abc", "--path", str(file_path), "--create"]
    if unique:
        args.append("--unique")
    if unlink_first:
        args.append("--unlink-first")

    result = CliRunner().invoke(cli, args)

    assert result.exit_code != 0
    assert "simulated" in result.output.lower() or "error" in result.output.lower()



def test_symlink_file_write_cli(tmp_path: Path):
    real_file = tmp_path / "real.txt"
    symlink = tmp_path / "link.txt"
    real_file.write_text("orig\n")
    symlink.symlink_to(real_file)
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "hello", "--path", str(symlink)])
    assert result.exit_code == 0
    assert real_file.read_text().endswith("hello\n")


def test_cli_basic_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "out.txt"
        line = "hello world"

        result = subprocess.run(
            [
                "filetool",
                "append",
                line,
                "--path",
                str(test_path),
                "--create",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Output must mention bytes written
        assert f"Wrote {len(line) + 1} bytes to {test_path}" in result.stdout

        # File must contain the expected line
        contents = test_path.read_bytes()
        assert contents == b"hello world\n"


@pytest.mark.parametrize(
    "create_if_missing, file_exists, expect_error",
    [
        (False, True, False),  # file exists, allowed
        (False, False, True),  # file missing, should raise
        (True, False, False),  # file missing, created
    ],
)
def test_append_bytes_to_file_basic(
    tmp_path: Path, create_if_missing, file_exists, expect_error
):
    test_file = tmp_path / "testfile.txt"

    if file_exists:
        test_file.write_bytes(b"existing\n")

    bytes_payload = b"new line\n"
    expected_content = b"existing\nnew line\n" if file_exists else b"new line\n"

    if expect_error:
        with pytest.raises(FileNotFoundError):
            append_bytes_to_file(
                bytes_payload=bytes_payload,
                path=test_file,
                unlink_first=False,
                unique_bytes=False,
                create_if_missing=create_if_missing,
                make_parents=False,
            )
    else:
        bytes_written = append_bytes_to_file(
            bytes_payload=bytes_payload,
            path=test_file,
            unlink_first=False,
            unique_bytes=False,
            create_if_missing=create_if_missing,
            make_parents=False,
        )
        assert bytes_written == len(bytes_payload)
        assert test_file.read_bytes() == expected_content



line_strategy = st.one_of(
    st.binary(min_size=1, max_size=256),  # typical payload
    st.just(b"\n"),  # newline only
    st.just(b"\x00"),  # null byte
    st.binary(min_size=255, max_size=256),  # max size
    st.binary(min_size=1, max_size=16).map(lambda x: x + b"\n"),  # ends in newline
    st.binary(min_size=1, max_size=16).map(lambda x: b"\n" + x),  # starts with newline
)


@pytest.mark.parametrize("unique_bytes", [False, True])
@pytest.mark.parametrize("unlink_first", [False, True])
@pytest.mark.parametrize("make_parents", [False, True])
@pytest.mark.parametrize("create_if_missing", [False, True])
@settings(
    max_examples=1000,
    deadline=None,
    phases=(Phase.generate, Phase.shrink),
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.large_base_example,
    ],
)
@given(line=line_strategy)
def test_write_line_fuzzed_line(
    create_if_missing, make_parents, unlink_first, unique_bytes, line
):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_path = tmp_path / "subdir" / "testfile"

        if unlink_first and not unique_bytes:
            with pytest.raises(ValueError):
                append_bytes_to_file(
                    bytes_payload=line,
                    path=test_path,
                    unique_bytes=unique_bytes,
                    create_if_missing=create_if_missing,
                    make_parents=make_parents,
                    unlink_first=unlink_first,
                )
            return

        if not create_if_missing and make_parents:
            with pytest.raises(ValueError):
                append_bytes_to_file(
                    bytes_payload=line,
                    path=test_path,
                    unique_bytes=unique_bytes,
                    line_ending=b"\n" if unique_bytes else None,
                    create_if_missing=create_if_missing,
                    make_parents=make_parents,
                    unlink_first=unlink_first,
                )
            return

        if make_parents:
            test_path.parent.mkdir(parents=True, exist_ok=True)

        if not unlink_first and create_if_missing:
            if not test_path.parent.exists():
                test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_bytes(b"")

        try:
            append_bytes_to_file(
                bytes_payload=line,
                path=test_path,
                unique_bytes=unique_bytes,
                line_ending=b"\n" if unique_bytes else None,
                create_if_missing=create_if_missing,
                make_parents=make_parents,
                unlink_first=unlink_first,
            )
        except FileNotFoundError:
            if not make_parents and not test_path.parent.exists():
                return
            raise

        assert test_path.exists()
        contents = test_path.read_bytes()
        if unique_bytes:
            assert contents.count(line) == 1
        else:
            assert contents.endswith(line)


@pytest.mark.parametrize("proc_count", [2, 4])
@settings(max_examples=10, deadline=None)
@given(line=line_strategy)
def test_multiprocess_append(proc_count, line):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_path = tmp_path / "subdir" / "mpfile"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.touch()

        def worker():
            append_bytes_to_file(
                bytes_payload=line,
                path=test_path,
                unique_bytes=False,
                create_if_missing=True,
                make_parents=True,
                unlink_first=False,
            )

        procs = [multiprocessing.Process(target=worker) for _ in range(proc_count)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()

        contents = test_path.read_bytes()
        assert contents.count(line) == proc_count


def test_process_append_bytes_to_file_chaos(tmp_path):
    test_path = tmp_path / "subdir" / "testfile"
    test_path.parent.mkdir(parents=True, exist_ok=True)

    base_payload = b"data"

    def chaos_worker(i: int):
        # Introduce random jitter
        time.sleep(random.uniform(0, 0.05))

        # Mutate the payload slightly per process
        payload = base_payload + f"-{i}".encode()

        try:
            append_bytes_to_file(
                bytes_payload=payload,
                path=test_path,
                unique_bytes=False,
                create_if_missing=True,
                make_parents=True,
                unlink_first=False,
            )
        except Exception as e:
            print(f"Process {i} exception: {e!r}")

    procs = [
        multiprocessing.Process(target=chaos_worker, args=(i,))
        for i in range(25)  # Turn this up as needed
    ]

    # Optional: simulate file vanishing mid-flight
    def chaos_interrupter():
        time.sleep(random.uniform(0.01, 0.03))
        if test_path.exists():
            os.unlink(test_path)
        # or: shutil.rmtree(test_path.parent)

    # Uncomment to activate chaos monkey
    # interrupter = multiprocessing.Process(target=chaos_interrupter)
    # interrupter.start()

    for p in procs:
        p.start()
    for p in procs:
        p.join()
    # if interrupter.is_alive():
    #     interrupter.terminate()

    result = test_path.read_bytes()
    for i in range(25):
        expected = base_payload + f"-{i}".encode()
        assert expected in result, f"Missing: {expected}"


@pytest.mark.parametrize("unique_bytes", [False, True])
@pytest.mark.parametrize("unlink_first", [False, True])
@pytest.mark.parametrize("make_parents", [False, True])
@pytest.mark.parametrize("create_if_missing", [False, True])
@pytest.mark.parametrize("proc_count", [2, 4])
@settings(max_examples=25, deadline=None)
@given(line=line_strategy)
def test_multiprocess_append_all_flags(
    proc_count, line, unique_bytes, unlink_first, make_parents, create_if_missing
):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_path = tmp_path / "subdir" / "mpfile"
        if make_parents:
            test_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            if create_if_missing:
                # mkdir if required to initialize
                test_path.parent.mkdir(parents=True)

        def worker():
            try:
                append_bytes_to_file(
                    bytes_payload=line,
                    path=test_path,
                    unique_bytes=unique_bytes,
                    create_if_missing=create_if_missing,
                    make_parents=make_parents,
                    unlink_first=unlink_first,
                )
            except Exception:
                pass  # Workers may race into errors we deliberately want to test

        procs = [multiprocessing.Process(target=worker) for _ in range(proc_count)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()

        if test_path.exists():
            contents = test_path.read_bytes()
            if unique_bytes:
                assert contents.count(line) <= 1
            else:
                expected = proc_count if not unlink_first else 1
                assert contents.count(line) in (
                    expected,
                    expected - 1,
                )  # allow 1 off due to race

    gc.collect()





class TrapRead(io.RawIOBase):
    def __init__(self, backing: bytes):
        self._buffer = io.BytesIO(backing)

    def read(self, size=-1):
        if size == -1:
            raise RuntimeError("Full read() call detected!")
        return self._buffer.read(size)

    def readinto(self, b: bytearray) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)

    def readable(self):
        return True

def test_splitlines_bytes_stream_does_not_load_entire_file():
    line = b"hello world\n"
    content = line * (10 * 1024 * 1024 // len(line))  # ~10 MB

    trap_stream = TrapRead(content)
    stream = io.BufferedReader(trap_stream)

    lines = list(splitlines_bytes(stream, delim=b"\n"))
    assert lines[0] == b"hello world\n"
    assert all(line == b"hello world\n" for line in lines)



@pytest.mark.skipif(not hasattr(psutil.Process(), "memory_info"), reason="psutil missing memory_info")
def test_splitlines_bytes_stream_memory_safe(tmp_path):
    # Efficiently create ~50MB file in one go
    line = b"data line goes here\n"
    total_bytes = 50 * 1024 * 1024
    repeated = total_bytes // len(line)
    big_file = tmp_path / "big_input.txt"
    big_file.write_bytes(line * repeated)  # MUCH faster than loop

    proc = psutil.Process()
    mem_before = proc.memory_info().rss

    # Scan file in streaming fashion
    with big_file.open("rb") as f:
        for _ in splitlines_bytes(f, delim=b"\n"):
            pass  # simulate processing

    time.sleep(0.05)  # allow RSS to settle (shorter is fine)
    mem_after = proc.memory_info().rss

    # Allow slight fluctuation due to Python overhead
    max_growth = 25 * 1024 * 1024
    assert mem_after - mem_before < max_growth, f"RSS grew too much: {mem_after - mem_before} bytes"

print("Checking for memory_info support:", hasattr(psutil.Process(), "memory_info"))

@pytest.mark.skipif(not hasattr(psutil.Process(), "memory_info"), reason="psutil missing memory_info")
def test_if_this_test_takes_forever_something_made_the_implementation_of_splitlines_bytes_is_too_slow(tmp_path):
    # Create ~50MB file
    line = b"data line goes here\n"
    count = 50 * 1024 * 1024 // len(line)
    big_file = tmp_path / "big_input.txt"
    with big_file.open("wb") as f:
        for _ in range(count):
            f.write(line)

    proc = psutil.Process()
    mem_before = proc.memory_info().rss

    with big_file.open("rb") as f:
        for _ in splitlines_bytes(f, delim=b"\n"):
            pass  # simulate processing

    time.sleep(0.1)  # ensure memory settles
    mem_after = proc.memory_info().rss

    # Assert memory did not grow unreasonably (>20MB spike)
    assert (mem_after - mem_before) < 20 * 1024 * 1024

