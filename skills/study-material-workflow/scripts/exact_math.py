"""Bounded rational arithmetic; no eval, symbolic proof or model calls."""
from workflow_common import WorkflowArgumentParser
import argparse
import ast
from fractions import Fraction
import operator
from workflow_common import cli_result, fail


def calculate(expression):
    if not isinstance(expression, str) or len(expression) > 1000:
        fail("invalid_expression", "Expression must be bounded text")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        fail("invalid_expression", str(exc))
    if len(list(ast.walk(tree))) > 200:
        fail("invalid_expression", "Too many expression nodes")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node, depth=0):
        if depth > 30:
            fail("invalid_expression", "Expression too deeply nested")
        if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) <= 10 ** 12:
            value = Fraction(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand, depth + 1) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            try:
                value = operations[type(node.op)](visit(node.left, depth + 1), visit(node.right, depth + 1))
            except ZeroDivisionError:
                fail("zero_denominator", "Rational denominator is zero")
        else:
            fail("unsupported_expression", "Only integer rational + - * / are supported")
        if value.numerator.bit_length() > 512 or value.denominator.bit_length() > 512:
            fail("invalid_expression", "Arithmetic result exceeds the bound")
        return value

    return visit(tree.body)


def main():
    parser = WorkflowArgumentParser(description=__doc__)
    parser.add_argument("expression")
    args = parser.parse_args()
    value = calculate(args.expression)
    return {"status": "checked", "numerator": value.numerator, "denominator": value.denominator,
            "proof_scope": "bounded rational arithmetic only"}


if __name__ == "__main__":
    raise SystemExit(cli_result(main))
