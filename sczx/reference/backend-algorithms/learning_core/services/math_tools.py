from __future__ import annotations

import ast
import io
import re
import tokenize

import sympy as sp

MATH_FUNCTIONS = {
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "log": sp.log,
    "exp": sp.exp,
    "abs": sp.Abs,
    "Abs": sp.Abs,
}
MATH_CONSTANTS = {"pi": sp.pi, "E": sp.E}


def normalize_expression(value: str) -> str:
    value = value.strip()
    # Remove complete presentation delimiters independently, including one
    # delimiter pair per blank. Unmatched source is deliberately not repaired.
    value = re.sub(
        r"\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$|\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]",
        lambda match: next(part for part in match.groups() if part is not None),
        value,
    )
    # Normalize bounded presentation syntax; the arithmetic AST below remains
    # the only parser. Unknown commands and malformed groups remain unverified.
    for _ in range(30):
        previous = value
        value = re.sub(
            r"\\(?:dfrac|tfrac|frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}",
            r"((\1)/(\2))", value,
        )
        value = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", value)
        if value == previous:
            break
    value = re.sub(r"\\(?:left|right)(?=[()])", "", value)
    value = value.replace(r"\times", "*").replace(r"\cdot", "*")
    # Translate only a bounded arithmetic exponent; unsupported TeX stays invalid.
    value = re.sub(r"\^\{([+-]?\d{1,3})\}", r"^(\1)", value)
    superscript_digits = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
    value = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", lambda match: "**" + match.group().translate(superscript_digits), value)
    return value.replace("×", "*").replace("÷", "/").replace("^", "**").replace("−", "-").strip()


def parse_math_expression(value: str) -> sp.Expr:
    """Build SymPy objects from a bounded arithmetic AST, never eval external text."""
    value = normalize_expression(value)
    if not value or len(value) > 500:
        raise ValueError("表达式长度超出可验证范围")
    if "\n" in value or "\r" in value or re.match(r"^\(\s*\d+\s*\).*\(\s*\d+\s*\)", value):
        raise ValueError("多行或分问答案需要逐项核对")
    tokens = list(tokenize.generate_tokens(io.StringIO(value).readline))
    pieces: list[str] = []
    previous: tokenize.TokenInfo | None = None
    for token in tokens:
        if token.type in {tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL}:
            continue
        if token.type not in {tokenize.NUMBER, tokenize.NAME, tokenize.OP}:
            raise ValueError("不支持的数学语法")
        if token.type == tokenize.OP and token.string not in {"+", "-", "*", "/", "**", "(", ")", ","}:
            raise ValueError("不支持的数学运算")
        if (
            token.type == tokenize.NAME
            and token.string not in MATH_FUNCTIONS
            and token.string not in MATH_CONSTANTS
        ):
            if len(token.string) != 1 or not token.string.isalpha():
                raise ValueError("只支持单字母变量")
        if previous:
            if token.type == tokenize.NUMBER and (previous.type == tokenize.NUMBER or previous.string == ")"):
                raise ValueError("相邻数值需要显式运算符，不能把分问答案作为乘法")
            ends_value = previous.type in {tokenize.NUMBER, tokenize.NAME} or previous.string == ")"
            starts_value = token.type in {tokenize.NUMBER, tokenize.NAME} or token.string == "("
            function_call = (
                previous.type == tokenize.NAME and previous.string in MATH_FUNCTIONS and token.string == "("
            )
            if ends_value and starts_value and not function_call:
                pieces.append("*")
        pieces.append(token.string)
        previous = token
    tree = ast.parse("".join(pieces), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("表达式过于复杂")

    def convert(node: ast.AST) -> sp.Expr:
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            if not -1e100 < node.value < 1e100:
                raise ValueError("数值超出可验证范围")
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name):
            if node.id in MATH_CONSTANTS:
                return MATH_CONSTANTS[node.id]
            if len(node.id) == 1 and node.id.isalpha():
                return sp.Symbol(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = convert(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = convert(node.left), convert(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div) and right != 0:
                if right.free_symbols:
                    raise ValueError("含变量分母的表达式需要结合定义域核对")
                return left / right
            if isinstance(node.op, ast.Pow) and right.is_number and abs(right) <= 20:
                if left.free_symbols and (right.is_integer is not True or right < 0):
                    raise ValueError("含变量负幂或分数幂的表达式需要结合定义域核对")
                if left.is_number and abs(left) > 1e100:
                    raise ValueError("幂运算超出可验证范围")
                if left.is_Pow and left.exp.is_number and abs(left.exp * right) > 100:
                    raise ValueError("幂运算超出可验证范围")
                return left**right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = MATH_FUNCTIONS.get(node.func.id)
            if function and not node.keywords and 1 <= len(node.args) <= (2 if node.func.id == "log" else 1):
                arguments = [convert(argument) for argument in node.args]
                if node.func.id in {"sqrt", "log", "tan"} and any(
                    argument.free_symbols for argument in arguments
                ):
                    raise ValueError("该函数需要结合定义域核对")
                if node.func.id == "exp" and arguments[0].is_number and abs(arguments[0]) > 100:
                    raise ValueError("指数运算超出可验证范围")
                return function(*arguments)
        raise ValueError("不支持的数学语法")

    result = convert(tree.body)
    if result.has(sp.zoo, sp.oo, -sp.oo, sp.nan):
        raise ValueError("表达式未定义")
    return result


def verify_equivalence(left: str, right: str) -> bool:
    return compare_equivalence(left, right)[0]


def compare_equivalence(left: str, right: str) -> tuple[bool, bool]:
    """Return equivalence plus whether both values were parsed symbolically."""
    try:
        equivalent = sp.simplify(parse_math_expression(left) - parse_math_expression(right)) == 0
        return bool(equivalent), True
    except Exception:  # Model/OCR text can trigger parser-internal exceptions too.
        return left.replace(" ", "") == right.replace(" ", ""), False


def solve_text_equation(text: str) -> tuple[str, bool]:
    # Only solve an explicitly requested standalone equation. A condition such as
    # "已知 2x+3=11，求 x²" must not replace the requested answer with x=4.
    candidate = normalize_expression(text).strip("。.!！?？ ")
    candidate = re.sub(
        r"^(?:解(?:一元一次)?方程|求解(?:方程)?|solve(?:\s+the)?(?:\s+equation)?)[：:\s]*",
        "",
        candidate,
        flags=re.I,
    )
    match = re.fullmatch(r"([^=]+)=([^=]+)", candidate)
    if not match:
        return "", False
    try:
        lhs = parse_math_expression(match.group(1))
        rhs = parse_math_expression(match.group(2))
        symbols = lhs.free_symbols | rhs.free_symbols
        if len(symbols) != 1:
            return "", False
        variable = next(iter(symbols))
        polynomial = sp.Poly(sp.together(lhs - rhs).as_numer_denom()[0], variable)
        if polynomial.degree() > 4:
            return "", False
        answers = sp.solveset(sp.Eq(lhs, rhs), variable, domain=sp.S.Reals)
        if not isinstance(answers, sp.FiniteSet) or not answers:
            return "", False
        return ", ".join(f"{variable}={item}" for item in sorted(answers, key=sp.default_sort_key)), True
    except Exception:  # Treat every malformed external expression as unverifiable.
        return "", False
