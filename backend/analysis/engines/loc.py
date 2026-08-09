import ast
import io
import tokenize
from pathlib import Path

from .base import BaseMetricEngine


class LOCEngine(BaseMetricEngine):

    def calculate(self, python_files: list[Path]) -> int:
        total_lines = 0

        for file_path in python_files:
            total_lines += self._count_file_lines(file_path)

        return total_lines

    @staticmethod
    def _count_file_lines(file_path: Path) -> int:
        source_code = file_path.read_text(encoding="utf-8")

        tree = ast.parse(source_code)

        docstring_lines = set()

        for node in ast.walk(tree):
            if isinstance(
                    node,
                    (
                            ast.Module,
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.ClassDef,
                    ),
            ):
                if ast.get_docstring(node) and node.body:
                    docstring = node.body[0]

                    if isinstance(docstring, ast.Expr):
                        value = docstring.value

                        if isinstance(value, ast.Constant) and isinstance(
                                value.value, str
                        ):
                            start = value.lineno
                            end = getattr(value, "end_lineno", start)

                            docstring_lines.update(
                                range(start, end + 1)
                            )

        code_lines = set()

        tokens = tokenize.generate_tokens(
            io.StringIO(source_code).readline
        )

        for token in tokens:
            if token.type in {
                tokenize.NAME,
                tokenize.NUMBER,
                tokenize.STRING,
                tokenize.OP,
            }:
                line = token.start[0]

                if line not in docstring_lines:
                    code_lines.add(line)

        return len(code_lines)