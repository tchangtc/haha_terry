"""Calculator tool - perform mathematical calculations."""

from __future__ import annotations

import ast
import math
import operator
from pathlib import Path

from . import BaseTool, tool_registry


class CalculatorTool(BaseTool):
    """Perform mathematical calculations and conversions."""

    name = "calculator"
    description = "Perform mathematical calculations, unit conversions, and formula evaluations."
    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate (e.g., '2+2', 'sqrt(16)', '10 USD to CNY')",
            },
        },
        "required": ["expression"],
    }

    # Maximum allowed value to prevent DoS attacks
    MAX_VALUE = 10**100
    # Maximum recursion depth for expressions
    MAX_RECURSION = 100

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

        # Safe math functions and constants
        self._safe_builtins = {
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'sum': sum,
            'pow': pow,
            'int': int,
            'float': float,
        }

        self._safe_math = {
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'log': math.log,
            'log10': math.log10,
            'log2': math.log2,
            'exp': math.exp,
            'ceil': math.ceil,
            'floor': math.floor,
            'factorial': math.factorial,
            'gcd': math.gcd,
        }

        self._safe_constants = {
            'pi': math.pi,
            'e': math.e,
            'tau': math.tau,
            'inf': math.inf,
        }

        self._safe_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
            ast.Lt: operator.lt,
            ast.Gt: operator.gt,
            ast.LtE: operator.le,
            ast.GtE: operator.ge,
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
        }

    def _safe_eval(self, node: ast.AST, depth: int = 0) -> float | int:
        """Safely evaluate an AST node without using eval().

        Args:
            node: AST node to evaluate
            depth: Current recursion depth

        Returns:
            Evaluated numeric result

        Raises:
            ValueError: On invalid or dangerous expressions
        """
        if depth > self.MAX_RECURSION:
            raise ValueError("Expression too complex (max recursion depth exceeded)")

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

        elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return node.n

        elif isinstance(node, ast.UnaryOp):
            op = self._safe_operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            operand = self._safe_eval(node.operand, depth + 1)
            return op(operand)

        elif isinstance(node, ast.BinOp):
            op = self._safe_operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            left = self._safe_eval(node.left, depth + 1)
            right = self._safe_eval(node.right, depth + 1)
            result = op(left, right)
            # Check for overflow
            if isinstance(result, (int, float)) and abs(result) > self.MAX_VALUE:
                raise ValueError("Result exceeds maximum allowed value")
            return result

        elif isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("Only simple comparisons are supported")
            left = self._safe_eval(node.left, depth + 1)
            right = self._safe_eval(node.comparators[0], depth + 1)
            op = self._safe_operators.get(type(node.ops[0]))
            if op is None:
                raise ValueError("Unsupported comparison operator")
            return 1 if op(left, right) else 0

        elif isinstance(node, ast.Name):
            name = node.id
            if name in self._safe_constants:
                return self._safe_constants[name]
            raise ValueError(f"Unknown name: {name}")

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are supported")
            func_name = node.func.id
            if func_name in self._safe_math:
                func = self._safe_math[func_name]
            elif func_name in self._safe_builtins:
                func = self._safe_builtins[func_name]
            else:
                raise ValueError(f"Unknown function: {func_name}")

            if len(node.args) > 5:
                raise ValueError(f"Too many arguments for function: {func_name}")

            args = [self._safe_eval(arg, depth + 1) for arg in node.args]
            result = func(*args)
            # Check for overflow
            if isinstance(result, (int, float)) and abs(result) > self.MAX_VALUE:
                raise ValueError("Result exceeds maximum allowed value")
            return result

        elif isinstance(node, ast.Expression):
            return self._safe_eval(node.body, depth)

        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")

    def execute(self, expression: str) -> str:
        """Execute calculation.

        Args:
            expression: Mathematical expression to evaluate

        Returns:
            Result message
        """
        try:
            # Check for unit conversion
            if " to " in expression.lower():
                return self._convert_units(expression)

            # Check for percentage calculation
            if "%" in expression:
                return self._calculate_percentage(expression)

            # Regular mathematical expression
            # Remove common formatting
            expr = expression.replace(",", "").replace(" ", "")

            # Parse and evaluate safely using AST
            tree = ast.parse(expr, mode='eval')
            result = self._safe_eval(tree)

            # Format result
            if isinstance(result, float):
                # Check if it's a whole number
                if result.is_integer():
                    result_str = str(int(result))
                else:
                    result_str = f"{result:.6g}"  # 6 significant figures
            else:
                result_str = str(result)

            return f"✓ {expression} = {result_str}"

        except ZeroDivisionError:
            return "Error: Division by zero"
        except SyntaxError:
            return f"Error: Invalid expression syntax: {expression}"
        except (ValueError, NameError) as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _convert_units(self, expression: str) -> str:
        """Convert units.

        Args:
            expression: Conversion expression (e.g., '10 USD to CNY', '100 km to miles')

        Returns:
            Conversion result
        """
        parts = expression.lower().split(" to ")
        if len(parts) != 2:
            return f"Error: Invalid conversion format: {expression}"

        from_part = parts[0].strip()
        to_unit = parts[1].strip()

        # Parse value and from_unit
        import re
        match = re.match(r'([\d.]+)\s*(.+)', from_part)
        if not match:
            return "Error: Invalid format. Use: <value> <from_unit> to <to_unit>"

        value = float(match.group(1))
        from_unit = match.group(2).strip()

        # Common conversions
        conversions = {
            # Length
            ('km', 'miles'): 0.621371,
            ('miles', 'km'): 1.60934,
            ('m', 'ft'): 3.28084,
            ('ft', 'm'): 0.3048,
            ('cm', 'in'): 0.393701,
            ('in', 'cm'): 2.54,

            # Weight
            ('kg', 'lb'): 2.20462,
            ('lb', 'kg'): 0.453592,
            ('g', 'oz'): 0.035274,
            ('oz', 'g'): 28.3495,

            # Temperature (special handling)
            ('c', 'f'): None,
            ('f', 'c'): None,
            ('celsius', 'fahrenheit'): None,
            ('fahrenheit', 'celsius'): None,

            # Currency (approximate rates - would need API for real-time)
            ('usd', 'cny'): 7.2,
            ('cny', 'usd'): 0.139,
            ('usd', 'eur'): 0.92,
            ('eur', 'usd'): 1.09,
            ('usd', 'jpy'): 150.0,
            ('jpy', 'usd'): 0.0067,
            ('usd', 'gbp'): 0.79,
            ('gbp', 'usd'): 1.27,
        }

        # Check for temperature conversion
        if from_unit in ['c', 'celsius'] and to_unit in ['f', 'fahrenheit']:
            result = (value * 9/5) + 32
            return f"✓ {value}°C = {result:.2f}°F"
        elif from_unit in ['f', 'fahrenheit'] and to_unit in ['c', 'celsius']:
            result = (value - 32) * 5/9
            return f"✓ {value}°F = {result:.2f}°C"

        # Check other conversions
        conversion_key = (from_unit, to_unit)
        if conversion_key in conversions:
            factor = conversions[conversion_key]
            result = value * factor

            # Format currency
            if from_unit in ['usd', 'eur', 'gbp', 'cny', 'jpy'] or to_unit in ['usd', 'eur', 'gbp', 'cny', 'jpy']:
                result_str = f"{result:.2f}"
            else:
                result_str = f"{result:.6g}"

            return f"✓ {value} {from_unit.upper()} = {result_str} {to_unit.upper()}"

        return f"Error: Conversion from {from_unit} to {to_unit} not supported"

    def _calculate_percentage(self, expression: str) -> str:
        """Calculate percentage.

        Args:
            expression: Percentage expression (e.g., '20% of 100', '50 is what % of 200')

        Returns:
            Percentage result
        """
        import re

        # Pattern: X% of Y
        match = re.match(r'([\d.]+)\s*%\s*of\s*([\d.]+)', expression, re.IGNORECASE)
        if match:
            percent = float(match.group(1))
            value = float(match.group(2))
            result = (percent / 100) * value
            return f"✓ {percent}% of {value} = {result:.2f}"

        # Pattern: X is what % of Y
        match = re.match(r'([\d.]+)\s*is\s*what\s*%\s*of\s*([\d.]+)', expression, re.IGNORECASE)
        if match:
            part = float(match.group(1))
            whole = float(match.group(2))
            if whole == 0:
                return "Error: Division by zero"
            result = (part / whole) * 100
            return f"✓ {part} is {result:.2f}% of {whole}"

        # Pattern: X is Y% of what
        match = re.match(r'([\d.]+)\s*is\s*([\d.]+)\s*%\s*of\s*what', expression, re.IGNORECASE)
        if match:
            part = float(match.group(1))
            percent = float(match.group(2))
            if percent == 0:
                return "Error: Percentage cannot be zero"
            result = (part * 100) / percent
            return f"✓ {part} is {percent}% of {result:.2f}"

        return f"Error: Invalid percentage expression: {expression}"


# Auto-register
tool_registry.register(CalculatorTool())
