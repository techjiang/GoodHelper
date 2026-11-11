"""心算：安全的算式求值，不做 eval。"""

from __future__ import annotations

import ast
import operator

from goodhelper.core.plugin import Reply, Rule, SimplePlugin

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def evaluate(expr: str) -> float:
    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        raise ValueError("只支持四则运算和乘方")

    return walk(ast.parse(expr, mode="eval"))


def _calc(ctx, match):
    expr = (match.group("expr") or "").strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    if not expr:
        return Reply("把算式给我，比如「算 12*(3+4)」。", "calc.empty")
    try:
        value = evaluate(expr)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
        return Reply(f"算不了：{exc}", "calc.error")
    pretty = int(value) if abs(value - round(value)) < 1e-9 else round(value, 8)
    return Reply(f"{expr} = {pretty}", "calc.ok", {"value": pretty})


PLUGIN = SimplePlugin(
    name="calc",
    title="计算",
    help=["算 12*(3+4)", "1+1"],
    rules=[
        # 「算」开头且不像自然语言的一律走计算器，好给出明确的拒绝而不是装懂
        Rule("calc", r"^(?:算|计算)\s*(?P<expr>.+)$", _calc, priority=40),
        Rule("calc", r"^(?P<expr>[-+*/%().\d\s×÷^]{3,})$", _calc, priority=60),
    ],
)
