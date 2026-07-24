"""Hardened sympy expression parsing.

`sympy.parsing.sympy_parser.parse_expr` (and `sympy.sympify`) parse their
input by compiling it to a Python expression and `eval`-ing it. With the
default (unrestricted) globals, that `eval` has full access to Python
builtins, so a string like `'__import__("os").system("echo PWNED")'` runs
arbitrary code -- confirmed via `_canonical_key` in math_generator.py.

`safe_parse_expr` is the one function every string-parsing call site in this
codebase should use instead of calling `parse_expr`/`sympify` directly.

Two layers of defense:
1. PRIMARY: parse with a locked-down namespace -- `global_dict` contains only
   sympy's public names (built once via `from sympy import *`) with
   `__builtins__` explicitly stripped, so names like `__import__`, `eval`,
   `os`, etc. simply don't resolve and Python builtins aren't reachable from
   the evaluated expression.
2. DEFENSE IN DEPTH: a cheap deny-list rejects strings containing obviously
   dangerous tokens (dunders, `import`, `lambda`, `exec`, `eval`, backticks)
   before parsing even starts, in case some other language feature is later
   found to reach builtins despite the restricted namespace.

Legitimate math strings (`"x**2 + 7*x + 10"`, `"2*(x+1)"`, `"sqrt(2)"`,
`"3/4"`, ...) are unaffected -- they don't need dunders/import/lambda/eval
and don't need Python builtins to resolve.
"""

import re

from sympy.parsing.sympy_parser import parse_expr as _sympy_parse_expr

# Built once: sympy's public namespace (Symbol, Integer, Rational, sqrt,
# sin, solve, ...) with builtins explicitly removed. parse_expr does not
# mutate the global_dict it's given (verified), so this is safe to reuse
# across calls.
_SAFE_GLOBALS: dict = {}
exec("from sympy import *", _SAFE_GLOBALS)  # noqa: S102 - trusted, static string
_SAFE_GLOBALS["__builtins__"] = {}

# Defense-in-depth deny-list: reject before parsing if any of these
# substrings appear. Legitimate expressions never contain them.
_DENYLIST_RE = re.compile(r"__|import|lambda|exec|eval|`")


class UnsafeExpressionError(ValueError):
    """Raised when an expression string is rejected before/during parsing."""


def safe_parse_expr(expr_str: str, **kwargs):
    """Parse `expr_str` into a sympy expression without allowing code
    execution.

    Raises `UnsafeExpressionError` (a `ValueError`) if the string is
    deny-listed or fails to parse under the restricted namespace. Callers
    should catch and fall back exactly as they did around the old
    `parse_expr`/`sympify` calls.
    """
    if _DENYLIST_RE.search(expr_str):
        raise UnsafeExpressionError(f"Rejected expression string: {expr_str!r}")

    kwargs.setdefault("global_dict", _SAFE_GLOBALS)
    kwargs.setdefault("local_dict", {})
    try:
        return _sympy_parse_expr(expr_str, **kwargs)
    except UnsafeExpressionError:
        raise
    except Exception as e:
        raise UnsafeExpressionError(f"Could not safely parse {expr_str!r}: {e}") from e
