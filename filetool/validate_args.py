#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

Constraint = dict[str, Any]


def _validate_args(
    *,
    function_name: str,
    args: dict,
    constraints: dict[str, Constraint],
    conflicts: list[tuple] | None = None,
) -> None:
    """
    Validate function arguments against a set of constraints.

    This function provides a declarative way to validate parameters with support for:
    - Type checking
    - Empty/non-empty validation
    - Parameter dependencies (requires, requires_if, requires_nonempty)
    - Conflict detection between parameters

    Parameters:
        function_name: Name of the function being validated (for error messages)
        args: Dictionary of argument names to values (typically from locals())
        constraints: Dictionary mapping parameter names to their validation rules
        conflicts: Optional list of conflict rules as tuples of (param_a, value_a, param_b, value_b, error_msg)

    Constraint rules:
        type: Required type or tuple of types for the parameter
        not_empty: If True, parameter must not be empty bytes (b"")
        nonempty_if_set: If True, parameter must not be empty if not None
        requires: List of parameter names that must be True when this parameter is True/set
        requires_if: List of (param, value) tuples - when this parameter is True/set,
                     the specified param must equal the specified value
        requires_nonempty: List of parameter names that must be non-empty when this parameter is True

    Raises:
        TypeError: If parameter type doesn't match constraint
        ValueError: If parameter violates a constraint or conflict rule

    Example:
        constraints = {
            "unique_bytes": {"type": bool},
            "line_ending": {
                "type": (bytes, type(None)),
                "nonempty_if_set": True,
                "requires": ["unique_bytes"],
            }
        }
        _validate_args(
            function_name="my_function",
            args=locals(),
            constraints=constraints,
        )
    """
    conflicts = conflicts or []

    for param, rules in constraints.items():
        val = args.get(param)

        # Type check
        if "type" in rules and not isinstance(val, rules["type"]):
            raise TypeError(
                f"{function_name}() {param} must be of type {rules['type']}, got {type(val).__name__}"
            )

        # Not empty check
        if rules.get("not_empty") and val == b"":
            raise ValueError(f"{function_name}() {param} must not be empty")

        # Must not be empty if set
        if rules.get("nonempty_if_set") and val is not None and len(val) == 0:
            raise ValueError(f"{function_name}() {param} must not be empty if set")

        # Requires other parameters
        if "requires" in rules:
            for required_param in rules["requires"]:
                required_val = args.get(required_param)
                if isinstance(val, bool):
                    if val and required_val is not True:
                        raise ValueError(
                            f"{function_name}() {param}=True requires {required_param}=True"
                        )
                elif val is not None and required_val is not True:
                    raise ValueError(
                        f"{function_name}() {param} requires {required_param}=True"
                    )

        # Requires specific parameter values when this parameter is True/set
        if "requires_if" in rules:
            for dep_param, expected_value in rules.get("requires_if", []):
                # Only check if this parameter is True (for bool) or not None (for others)
                if isinstance(val, bool):
                    if val and args.get(dep_param) != expected_value:
                        raise ValueError(
                            f"{function_name}() {param}=True requires {dep_param}={expected_value}"
                        )
                elif val is not None:
                    if args.get(dep_param) != expected_value:
                        raise ValueError(
                            f"{function_name}() {param}={val} requires {dep_param}={expected_value}"
                        )

        # Requires nonempty parameters if this is True
        if "requires_nonempty" in rules:
            for required_param in rules["requires_nonempty"]:
                required_val = args.get(required_param)
                if val is True and (required_val is None or len(required_val) == 0):
                    raise ValueError(
                        f"{function_name}() {param}=True requires {required_param} to be non-empty"
                    )

    # Conflicts (apply unconditionally)
    for a, a_val, b, b_val, msg in conflicts:
        if args.get(a) == a_val and args.get(b) == b_val:
            raise ValueError(f"{function_name}()" + msg)
