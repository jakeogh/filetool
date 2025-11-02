"""
isort:skip_file
"""

from .filetool import _append_bytes_to_file as _append_bytes_to_file
from .filetool import comment_out_line_in_file as comment_out_line_in_file
from .filetool import uncomment_line_in_file as uncomment_line_in_file
from .filetool import ensure_line_in_config_file as ensure_line_in_config_file

from .append_line_to_file import append_line_to_file as append_line_to_file
from .append_bytes_to_file import append_bytes_to_file as append_bytes_to_file

from .cli import cli as cli

# Define public API explicitly
__all__ = [
    "append_line_to_file",
    "append_bytes_to_file",
    "comment_out_line_in_file",
    "cli",
]
