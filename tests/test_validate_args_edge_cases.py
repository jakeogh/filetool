#!/usr/bin/env python3
"""
Tests for _validate_args edge cases and error paths.
"""

import pytest

from filetool.validate_args import _validate_args


def test_validate_args_type_check():
    """Test that _validate_args validates parameter types."""
    constraints = {
        "test_param": {
            "type": bytes,
        }
    }

    # Should raise TypeError for wrong type
    with pytest.raises(TypeError, match="test_param must be of type"):
        _validate_args(
            function_name="test_function",
            args={"test_param": "not bytes"},
            constraints=constraints,
        )


def test_validate_args_not_empty_check():
    """Test that _validate_args validates not_empty constraint."""
    constraints = {
        "test_param": {
            "type": bytes,
            "not_empty": True,
        }
    }

    # Should raise ValueError for empty bytes
    with pytest.raises(ValueError, match="test_param must not be empty"):
        _validate_args(
            function_name="test_function",
            args={"test_param": b""},
            constraints=constraints,
        )


def test_validate_args_nonempty_if_set_check():
    """Test that _validate_args validates nonempty_if_set constraint."""
    constraints = {
        "test_param": {
            "type": (bytes, type(None)),
            "nonempty_if_set": True,
        }
    }

    # Should raise ValueError for empty bytes when set
    with pytest.raises(ValueError, match="test_param must not be empty if set"):
        _validate_args(
            function_name="test_function",
            args={"test_param": b""},
            constraints=constraints,
        )

    # Should pass for None
    _validate_args(
        function_name="test_function",
        args={"test_param": None},
        constraints=constraints,
    )


def test_validate_args_requires_check():
    """Test that _validate_args validates requires constraint."""
    constraints = {
        "param_a": {
            "type": bool,
            "requires": ["param_b"],
        },
        "param_b": {
            "type": bool,
        },
    }

    # Should raise ValueError when param_a=True but param_b is not True
    with pytest.raises(ValueError, match="param_a=True requires param_b=True"):
        _validate_args(
            function_name="test_function",
            args={"param_a": True, "param_b": False},
            constraints=constraints,
        )


def test_validate_args_requires_if_check():
    """Test that _validate_args validates requires_if constraint."""
    constraints = {
        "param_a": {
            "type": (bool, type(None)),
            "requires_if": [("param_b", True)],
        },
        "param_b": {
            "type": bool,
        },
    }

    # Should raise ValueError when param_a is set but param_b != True
    with pytest.raises(ValueError, match="param_a=True requires param_b=True"):
        _validate_args(
            function_name="test_function",
            args={"param_a": True, "param_b": False},
            constraints=constraints,
        )

    # Should pass when param_b has the required value
    _validate_args(
        function_name="test_function",
        args={"param_a": True, "param_b": True},
        constraints=constraints,
    )


def test_validate_args_requires_nonempty_check():
    """Test that _validate_args validates requires_nonempty constraint."""
    constraints = {
        "param_a": {
            "type": bool,
            "requires_nonempty": ["param_b"],
        },
        "param_b": {
            "type": bytes,
        },
    }

    # Should raise ValueError when param_a=True but param_b is empty
    with pytest.raises(
        ValueError, match="param_a=True requires param_b to be non-empty"
    ):
        _validate_args(
            function_name="test_function",
            args={"param_a": True, "param_b": b""},
            constraints=constraints,
        )

    # Should raise ValueError when param_a=True but param_b is None
    with pytest.raises(
        ValueError, match="param_a=True requires param_b to be non-empty"
    ):
        _validate_args(
            function_name="test_function",
            args={"param_a": True, "param_b": None},
            constraints=constraints,
        )


def test_validate_args_conflicts_check():
    """Test that _validate_args validates conflicts."""
    constraints = {}
    conflicts = [
        ("param_a", True, "param_b", True, "param_a and param_b cannot both be True"),
    ]

    # Should raise ValueError when both params are True
    with pytest.raises(ValueError, match="param_a and param_b cannot both be True"):
        _validate_args(
            function_name="test_function",
            args={"param_a": True, "param_b": True},
            constraints=constraints,
            conflicts=conflicts,
        )


def test_validate_args_passes_valid_args():
    """Test that _validate_args passes for valid arguments."""
    constraints = {
        "test_param": {
            "type": bytes,
            "not_empty": True,
        }
    }

    # Should not raise for valid args
    _validate_args(
        function_name="test_function",
        args={"test_param": b"valid"},
        constraints=constraints,
    )
