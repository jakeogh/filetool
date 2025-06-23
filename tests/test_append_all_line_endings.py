import pytest
from pathlib import Path
from click.testing import CliRunner
from filetool.cli import cli

@pytest.mark.parametrize("hex_byte", [f"{i:02x}" for i in range(256)])
def test_unique_appends_once_with_line_ending(tmp_path: Path, hex_byte: str):
    runner = CliRunner()
    path = tmp_path / "file.txt"
    line = b"data"
    line_ending = bytes.fromhex(hex_byte)
    full_line = line + line_ending

    # Step 1: Pre-fill with the line to trigger deduplication
    path.write_bytes(full_line)

    # Step 2: Attempt to append again with --unique (should not write)
    result = runner.invoke(cli, [
        "append", "--path", str(path), "--create",
        "--unique", "--line-ending-hex", hex_byte,
        "--hex-input", line.hex()
    ])
    assert result.exit_code == 0
    assert path.read_bytes() == full_line

    # Step 3: Clear the file, try again (should write now)
    path.unlink()
    result = runner.invoke(cli, [
        "append", "--path", str(path), "--create",
        "--unique", "--line-ending-hex", hex_byte,
        "--hex-input", line.hex()
    ])
    assert result.exit_code == 0
    assert path.read_bytes() == full_line


@pytest.mark.parametrize("hex_byte", [f"{i:02x}" for i in range(256)])
def test_line_ending_requires_unique(tmp_path: Path, hex_byte: str):
    runner = CliRunner()
    path = tmp_path / "file.txt"
    result = runner.invoke(cli, [
        "append", "--path", str(path), "--create",
        "--line-ending-hex", hex_byte,
        "--hex-input", "deadbeef"
    ])
    assert result.exit_code != 0
    assert "--line-ending-hex --requires --unique" in result.output
