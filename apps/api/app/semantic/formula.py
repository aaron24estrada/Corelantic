"""Validate a derived metric's formula — the grammar authority, load-time and pure.

A formula is a deliberately tiny language: component-measure *names*, numeric literals,
and the binary operators ``+ - * /`` (plus unary minus). This module parses it with
Python's ``ast`` and confirms every node is on that allowlist and every name is one of
the metric's declared measures — raising ``InvalidFormulaError`` otherwise, at registry
load, before any query runs.

It is the single authority on what a formula may contain. ``app/query/formula.py`` calls
``validate_formula`` before translating the same expression into a SQLAlchemy Core tree,
so the SQL builder only ever walks an already-approved expression. Kept SQLAlchemy-free
so the loader can use it without ``query`` depending backwards on ``semantic``.
"""

import ast
import math

from app.semantic.errors import InvalidFormulaError

ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def validate_formula(expression: str, allowed: set[str]) -> None:
    """Raise ``InvalidFormulaError`` unless the formula is on the allowlist.

    ``allowed`` is the set of names the formula may reference — the metric's declared
    measures plus the registry's constants.
    """

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise InvalidFormulaError(expression, "not a parseable expression") from exc
    _check(tree.body, expression, allowed)


def formula_names(expression: str) -> set[str]:
    """The names a formula references. Call only on an expression ``validate_formula`` passed."""

    tree = ast.parse(expression, mode="eval")
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def formula_is_linear(expression: str, measures: set[str]) -> bool:
    """Whether the formula is degree ≤ 1 in ``measures``, treating every other name as constant.

    This is what decides whether a derived metric may be accumulated: summing a period's values
    equals the value of the summed periods only when the formula is linear. ``vouchers * fee``
    is; ``(revenue - spend) / revenue`` is not, because dividing by a measure is not a
    polynomial in it at all. Call only on an expression ``validate_formula`` has passed.
    """

    degree = _degree(ast.parse(expression, mode="eval").body, measures)
    return degree is not None and degree <= 1


def _degree(node: ast.expr, measures: set[str]) -> int | None:
    """The polynomial degree of ``node`` in ``measures``; None when it is not a polynomial."""

    if isinstance(node, ast.Name):
        return 1 if node.id in measures else 0
    if isinstance(node, ast.Constant):
        return 0
    if isinstance(node, ast.UnaryOp):
        return _degree(node.operand, measures)
    if isinstance(node, ast.BinOp):
        left = _degree(node.left, measures)
        right = _degree(node.right, measures)
        if left is None or right is None:
            return None
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return max(left, right)
        if isinstance(node.op, ast.Mult):
            return left + right
        # Division: only by something free of measures keeps it a polynomial.
        return None if right > 0 else left
    raise AssertionError(f"unvalidated node reached _degree: {type(node).__name__}")


def _check(node: ast.expr, expression: str, allowed: set[str]) -> None:
    if isinstance(node, ast.Name):
        if node.id not in allowed:
            raise InvalidFormulaError(
                expression, f"{node.id!r} is not a declared measure or constant {sorted(allowed)}"
            )
        return
    if isinstance(node, ast.Constant):
        # bool is a subtype of int — exclude it; only finite numbers are meaningful.
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise InvalidFormulaError(expression, "only numeric literals are allowed")
        if isinstance(node.value, float) and not math.isfinite(node.value):
            raise InvalidFormulaError(expression, "non-finite numeric literal")
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _check(node.operand, expression, allowed)
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BINOPS):
        _check(node.left, expression, allowed)
        _check(node.right, expression, allowed)
        return
    raise InvalidFormulaError(expression, f"{type(node).__name__} is not allowed")
