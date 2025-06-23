import os
from pathlib import Path
from click.testing import CliRunner
import pytest
from filetool.cli import cli

@pytest.fixture
def tmpfile(tmp_path):
    return tmp_path / "file.txt"

def test_append_base_case(tmpfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["append", "--path", str(tmpfile), "--create", "--unique", "--line-ending-hex", "0a", "base"])
    assert result.exit_code == 0
    assert tmpfile.read_bytes() == b"base\n"

@pytest.mark.parametrize("use_unique", [False, True])
def test_append_base_case_unique_behavior(tmpfile, use_unique):
    tmpfile.write_text("base\n")
    runner = CliRunner()

    args = ["append", "--path", str(tmpfile), "--create"]
    if use_unique:
        args += ["--unique", "--line-ending-hex", "0a"]
    args.append("base")

    result = runner.invoke(cli, args)
    assert result.exit_code == 0

    content = tmpfile.read_bytes()
    if use_unique:
        assert content == b"base\n"
    else:
        assert content == b"base\nbase\n"

@pytest.mark.parametrize("line_ending_hex", [f"{i:02x}" for i in range(256)])
@pytest.mark.parametrize("use_unique", [False, True])
@pytest.mark.parametrize("do_not_append_line_ending", [False, True])
@pytest.mark.parametrize("hex_input", [False, True])
def test_append_line_ending_hex_behavior(tmpfile, line_ending_hex, use_unique, do_not_append_line_ending, hex_input,):
    runner = CliRunner()
    data = b"line"
    ending = bytes.fromhex(line_ending_hex)

    #if use_unique:
    tmpfile.write_bytes(data + ending)
    print(f"{repr(tmpfile.read_bytes())=}")

    print(f"{line_ending_hex=}", f"{use_unique=}", f"{ending=}", f"{do_not_append_line_ending=}", f"{hex_input=}")

    args = ["append", "--path", str(tmpfile), "--create"]

    if hex_input:
        args += ["--hex-input"]
        args += [data.hex()]
    else:
        args += [data]

    if do_not_append_line_ending:
        args += ["--do-not-append-line-ending"]

    if use_unique:
        args += ["--unique", "--line-ending-hex", line_ending_hex]
    else:
        args += ["--line-ending-hex", line_ending_hex]

    print(f"{args=}")
    result = runner.invoke(cli, args)

    if use_unique:
        if not do_not_append_line_ending:
            if hex_input:
                assert result.exit_code == 1
                assert "--hex-input requires --do-not-append-line-ending" in result.output
            else:
                print(f"{result.exit_code=}")
                print(f"{result.output=}")
                assert result.exit_code == 0
                assert tmpfile.read_bytes() == data + ending
                #assert False
        else:
            if hex_input:
                assert result.exit_code == 0
                assert tmpfile.read_bytes() == data + ending + data  # the line did not match, because it did not end in `ending`, so --unique did not match. This is normal when using --hex-input.
            else:
                assert result.exit_code == 0
                assert tmpfile.read_bytes() == data + ending
    else:
        if do_not_append_line_ending:
            if hex_input:
                assert result.exit_code != 0
                assert "--line-ending-hex has no effect when --do-not-append-line-ending is used without --unique" in result.output
            else:
                print(f"{result.exit_code=}")
                print(f"{result.output=}")
                assert False
        else:
            if hex_input:
                assert result.exit_code == 1
                assert "--hex-input requires --do-not-append-line-ending" in result.output
            else:
                #print(f"{result.exit_code=}")
                #print(f"{result.output=}")
                assert result.exit_code == 0
                assert tmpfile.read_bytes() == data + ending + data + ending
