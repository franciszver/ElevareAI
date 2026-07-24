"""Hardened sympy expression parsing.

`sympy.parsing.sympy_parser.parse_expr` (and `sympy.sympify`) parse their
input by compiling it to a Python expression and `eval`-ing it. With the
default (unrestricted) globals, that `eval` has full access to Python
builtins, so a string like `'__import__("os").system("echo PWNED")'` runs
arbitrary code -- confirmed via `_canonical_key` in math_generator.py.

`safe_parse_expr` is the one function every string-parsing call site in this
codebase should use instead of calling `parse_expr`/`sympify` directly.

Two layers of defense:
1. PRIMARY (the real control): parse with an explicit ALLOWLIST namespace
   containing ONLY safe math constructors/functions/constants -- built by
   importing curated names one at a time, never via `from sympy import *`.
   Critically, this means `sympify`, `S`, `parse_expr`, `lambdify`, and any
   other sympy helper that re-parses a *string* argument (with its OWN,
   unrestricted default globals) or compiles+execs generated source are
   ABSENT from the namespace. Without them, a payload like
   `sympify("_" + "_" + "imp" + "ort" + ... )` can't reach code execution at
   all: with `sympify` undefined in the namespace, `parse_expr`'s
   auto-symbol transformation turns the bare name `sympify` into an inert
   undefined Sympy Function/Symbol instead of a call to the real
   `sympy.sympify` -- there's simply nothing in the namespace capable of
   parsing/eval-ing/compiling a string at all, regardless of how that
   string was assembled. `__builtins__` is also stripped, so raw builtins
   (`__import__`, `eval`, `exec`, ...) aren't reachable either.
2. DEFENSE IN DEPTH: a cheap deny-list rejects strings containing a couple
   of obviously dangerous tokens before parsing even starts, in case some
   other avenue to builtins is found later. Kept intentionally minimal
   (just dunders and backticks) now that the allowlist -- not the deny-list
   -- is the real control: a broader deny-list (e.g. matching the substring
   `eval`) previously false-rejected legitimate strings containing sympy's
   `evalf` method name.

Legitimate math strings (`"x**2 + 7*x + 10"`, `"2*(x+1)"`, `"sqrt(2)"`,
`"3/4"`, ...) are unaffected -- they don't need dunders/import/lambda/eval
and don't need Python builtins, sympify, S, or lambdify to resolve.
"""

import re

import sympy
from sympy.parsing.sympy_parser import parse_expr as _sympy_parse_expr

# Explicit allowlist of safe names to expose to parsed expressions. This is
# the PRIMARY security control (see module docstring): every name here is a
# constructor/function/constant, never something that re-parses a string or
# compiles/execs code (no sympify, S, parse_expr, lambdify, preview, srepr,
# etc.). Determined empirically -- start from a safe core, then run the
# full test suite and add only the specific names legit tests need.
_ALLOWED_NAMES = [
    # Symbols / core constructors
    "Symbol",
    "Integer",
    "Rational",
    "Float",
    "Eq",
    "Abs",
    # Constants
    "pi",
    "E",
    "I",
    "oo",
    "zoo",
    "nan",
    # Powers / roots
    "sqrt",
    "root",
    "exp",
    "log",
    "ln",
    # Trig / hyperbolic
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sinh",
    "cosh",
    "tanh",
    # Combinatorics / number theory
    "factorial",
    "binomial",
    "gcd",
    "lcm",
    # Rounding / sign
    "floor",
    "ceiling",
    "sign",
]

# Built once: an explicit allowlist of sympy names (see _ALLOWED_NAMES
# above) with `__builtins__` explicitly removed. parse_expr does not mutate
# the global_dict it's given (verified), so this is safe to reuse across
# calls.
_SAFE_GLOBALS: dict = {name: getattr(sympy, name) for name in _ALLOWED_NAMES}
_SAFE_GLOBALS["__builtins__"] = {}

# Defense-in-depth deny-list: reject before parsing if any of these
# substrings appear. Kept minimal now that the allowlist above is the real
# control -- a broader list (e.g. matching bare "eval") previously
# false-rejected legitimate strings containing sympy's `evalf` method name.
_DENYLIST_RE = re.compile(r"__|`")


class UnsafeExpressionError(ValueError):
    """Raised when an expression string is rejected before/during parsing."""


def safe_parse_expr(expr_str: str, **kwargs):
    """Parse `expr_str` into a sympy expression without allowing code
    execution.

    Raises `UnsafeExpressionError` (a `ValueError`) if the string is
    deny-listed or fails to parse under the restricted namespace. Callers
    should catch and fall back exactly as they did around the old
    `parse_expr`/`sympify` calls.

    `global_dict`/`local_dict` are always forced to the sandboxed allowlist,
    never taken from the caller -- a caller-supplied `global_dict` could
    otherwise quietly reintroduce `sympify`/`eval`/builtins and bypass the
    sandbox. No current caller passes them (all just pass `expr_str`).
    """
    if _DENYLIST_RE.search(expr_str):
        raise UnsafeExpressionError(f"Rejected expression string: {expr_str!r}")

    kwargs["global_dict"] = _SAFE_GLOBALS
    kwargs["local_dict"] = {}
    try:
        return _sympy_parse_expr(expr_str, **kwargs)
    except UnsafeExpressionError:
        raise
    except Exception as e:
        raise UnsafeExpressionError(f"Could not safely parse {expr_str!r}: {e}") from e
