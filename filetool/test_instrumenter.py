#!/usr/bin/env python3
"""
Function instrumenter for testing race conditions and attack scenarios.

This module provides utilities to dynamically instrument functions by injecting
hook callbacks at marked points (# HOOK:name comments). This allows tests to
synchronize with specific steps in the implementation and execute attacks or
verification at precise moments.

Usage:
    from test_instrumenter import instrument_function

    hooks = {
        'step_12_read_lines': lambda ctx: attacker_thread.start(),
        'step_13_stat_after_read': lambda ctx: verify_file_deleted(),
    }

    instrumented_func = instrument_function(original_func, hooks)
    result = instrumented_func(path=Path('/etc/config'), ...)
"""

import inspect
import textwrap
from collections.abc import Callable


class HookContext:
    """
    Context passed to hook callbacks with information about execution state.

    Attributes:
        hook_name: Name of the hook (e.g., 'step_12_read_lines')
        locals: Local variables at the hook point (read-only snapshot)
        function_name: Name of the instrumented function
    """

    def __init__(
        self,
        hook_name: str,
        locals_snapshot: dict,
        function_name: str,
    ):
        self.hook_name = hook_name
        self.locals = locals_snapshot.copy()
        self.function_name = function_name

    def __repr__(self):
        return f"HookContext(hook={self.hook_name}, func={self.function_name})"


def instrument_function(
    func: Callable,
    hooks: dict[str, Callable[[HookContext], None]],
    *,
    verbose: bool = False,
) -> Callable:
    """
    Instrument a function by injecting hook callbacks at marked points.

    This function scans the source code for comments in the format:
        # HOOK:hook_name

    And injects a callback invocation immediately after each such comment.
    The callback receives a HookContext with information about the execution state.

    Args:
        func: The function to instrument (must have # HOOK: comments in source)
        hooks: Dict mapping hook names to callback functions
               Callback signature: (HookContext) -> None
        verbose: If True, print instrumentation details for debugging

    Returns:
        Instrumented function with the same signature as the original

    Raises:
        ValueError: If function source cannot be retrieved
        SyntaxError: If modified source has syntax errors

    Example:
        def my_function(x: int) -> int:
            # HOOK:before_calculation
            result = x * 2
            # HOOK:after_calculation
            return result

        def my_hook(ctx: HookContext):
            print(f"Hook {ctx.hook_name} called with locals: {ctx.locals}")

        instrumented = instrument_function(
            my_function,
            {
                'before_calculation': my_hook,
                'after_calculation': my_hook,
            }
        )

        instrumented(5)  # Hooks will be called during execution

    Implementation notes:
        - Creates a modified version of the function with hook calls injected
        - Preserves original function's signature, docstring, and name
        - Hook callbacks are executed synchronously in the same thread
        - Exceptions in hooks propagate to caller (hooks should be defensive)
        - Local variables are captured as read-only snapshots
    """

    # Get the source code of the function
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError) as e:
        raise ValueError(f"Cannot get source for function {func.__name__}: {e}")

    # Dedent to normalize indentation
    source = textwrap.dedent(source)
    lines = source.split("\n")

    # Find all hook points and inject callback invocations
    modified_lines = []
    hooks_injected = []

    for i, line in enumerate(lines):
        modified_lines.append(line)

        # Check if this line has a hook marker
        if "# HOOK:" in line:
            # Extract hook name
            hook_name = line.split("# HOOK:")[1].strip()
            hooks_injected.append(hook_name)

            # Determine indentation level
            indent = len(line) - len(line.lstrip())
            indent_str = " " * indent

            # Inject hook callback invocation
            # We create a HookContext and call the hook if it's registered
            hook_call = f"{indent_str}_hook_callback('{hook_name}', locals(), '{func.__name__}')"
            modified_lines.append(hook_call)

    # Build the modified source
    modified_source = "\n".join(modified_lines)

    if verbose:
        print(f"=== Instrumenting {func.__name__} ===")
        print(f"Found {len(hooks_injected)} hook points: {hooks_injected}")
        print(f"Registered hooks: {list(hooks.keys())}")
        print("\n=== Modified source ===")
        print(modified_source)
        print("=" * 50)

    # Define the hook callback dispatcher that will be available in the exec environment
    def _hook_callback(
        hook_name: str,
        locals_snapshot: dict,
        function_name: str,
    ):
        """Internal callback dispatcher injected into instrumented function."""
        if hook_name in hooks:
            ctx = HookContext(
                hook_name,
                locals_snapshot,
                function_name,
            )
            hooks[hook_name](ctx)

    # Prepare execution environment
    # We need to include all the globals that the original function had access to
    exec_globals = func.__globals__.copy()
    exec_globals["_hook_callback"] = _hook_callback

    # Compile and execute the modified function definition
    try:
        exec(modified_source, exec_globals)
    except SyntaxError as e:
        print("=== SYNTAX ERROR IN MODIFIED SOURCE ===")
        print(modified_source)
        print("=" * 50)
        raise SyntaxError(f"Failed to compile instrumented function: {e}")

    # Retrieve the newly created function from the execution environment
    instrumented_func = exec_globals[func.__name__]

    # Preserve metadata
    instrumented_func.__doc__ = func.__doc__
    instrumented_func.__name__ = func.__name__
    instrumented_func.__module__ = func.__module__

    return instrumented_func


def create_synchronization_hook(barrier, event=None):
    """
    Create a hook that synchronizes with another thread using a barrier.

    Useful for coordinating attacker threads with victim execution.

    Args:
        barrier: threading.Barrier to wait on
        event: Optional threading.Event to set after barrier

    Returns:
        Hook callback function

    Example:
        import threading

        barrier = threading.Barrier(2)  # Main thread + attacker thread

        def attacker():
            barrier.wait()  # Wait for hook to be reached
            # Execute attack here

        hooks = {
            'step_12_read_lines': create_synchronization_hook(barrier),
        }

        attacker_thread = threading.Thread(target=attacker)
        attacker_thread.start()

        instrumented_func(...)  # Will pause at hook, letting attacker run
        attacker_thread.join()
    """

    def hook(ctx: HookContext):
        barrier.wait()
        if event:
            event.set()

    return hook


def create_assertion_hook(assertion_func):
    """
    Create a hook that runs an assertion at a specific point.

    Args:
        assertion_func: Function that takes HookContext and raises AssertionError on failure

    Returns:
        Hook callback function

    Example:
        def check_file_exists(ctx: HookContext):
            path = ctx.locals['path']
            assert path.exists(), f"File {path} should exist at {ctx.hook_name}"

        hooks = {
            'step_13_stat_after_read': create_assertion_hook(check_file_exists),
        }
    """

    def hook(ctx: HookContext):
        assertion_func(ctx)

    return hook


def create_logging_hook(log_func=print):
    """
    Create a hook that logs execution progress.

    Args:
        log_func: Function to call with log messages (default: print)

    Returns:
        Hook callback function

    Example:
        hooks = {
            'step_12_read_lines': create_logging_hook(lambda msg: print(f"[LOG] {msg}")),
        }
    """

    def hook(ctx: HookContext):
        log_func(f"Hook {ctx.hook_name} in {ctx.function_name}()")

    return hook


def create_state_capture_hook(state_dict: dict, key: str):
    """
    Create a hook that captures local variables into a shared dict.

    Args:
        state_dict: Dict to store captured state
        key: Key to use in state_dict

    Returns:
        Hook callback function

    Example:
        captured_state = {}

        hooks = {
            'step_5_record_inode': create_state_capture_hook(captured_state, 'inode_before'),
            'step_26_compare_inode_before_rename': create_state_capture_hook(captured_state, 'inode_after'),
        }

        instrumented_func(...)

        # After execution:
        assert captured_state['inode_before'] == captured_state['inode_after']
    """

    def hook(ctx: HookContext):
        state_dict[key] = ctx.locals.copy()

    return hook


if __name__ == "__main__":
    # Self-test
    def example_function(x: int) -> int:
        """Example function with hooks for testing."""
        # HOOK:start
        y = x * 2
        # HOOK:middle
        z = y + 1
        # HOOK:end
        return z

    call_log = []

    def log_hook(ctx: HookContext):
        call_log.append(ctx.hook_name)
        print(f"Hook: {ctx.hook_name}, locals: {ctx.locals}")

    instrumented = instrument_function(
        example_function,
        {
            "start": log_hook,
            "middle": log_hook,
            "end": log_hook,
        },
        verbose=True,
    )

    result = instrumented(5)
    print(f"\nResult: {result}")
    print(f"Hooks called: {call_log}")
    assert call_log == ["start", "middle", "end"]
    assert result == 11
    print("\n✓ Self-test passed!")
