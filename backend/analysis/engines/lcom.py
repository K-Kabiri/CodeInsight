import ast
from pathlib import Path

from .base import BaseMetricEngine


class LCOMEngine(BaseMetricEngine):
    """
    Lack of Cohesion of Methods (LCOM1).

    Based on the original Chidamber and Kemerer
    definition of LCOM.

    For a class:

        P = number of method pairs that do not
            share access to any instance attribute.

        Q = number of method pairs that share
            access to at least one instance attribute.

        LCOM = max(P - Q, 0)

    Only attributes belonging to the class instance
    (accessed through self) are considered.
    """

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> int:
        """
        Calculate total LCOM across all classes.
        """

        result = self.calculate_detailed(
            python_files,
            scope,
        )

        return result["total"]

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:
        """
        Calculate LCOM for every class.
        """

        files = []
        all_scores = []

        for file_path in python_files:
            result = self._analyze_file(
                file_path
            )

            files.append(result)

            all_scores.extend(
                item["lcom"]
                for item in result["classes"]
            )

        total = sum(all_scores)

        average = (
            total / len(all_scores)
            if all_scores
            else 0.0
        )

        return {
            "metric": "LCOM",
            "total": total,
            "average": average,
            "class_count": len(all_scores),
            "files": files,
        }

    # File analysis
    @staticmethod
    def _analyze_file(
            file_path: Path,
    ) -> dict:
        source_code = file_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source_code,
            filename=str(file_path),
        )

        visitor = _LCOMVisitor()

        visitor.visit(tree)

        return {
            "file": str(file_path),
            "total": sum(
                item["lcom"]
                for item in visitor.classes
            ),
            "classes": visitor.classes,
        }


# Class context
class _LCOMClassContext:

    def __init__(
            self,
            name: str,
            lineno: int,
            endline: int,
    ):
        self.name = name
        self.lineno = lineno
        self.endline = endline

        self.methods = []

    def add_method(
            self,
            name: str,
            lineno: int,
            endline: int,
            attributes: set[str],
    ):

        self.methods.append(
            {
                "name": name,
                "lineno": lineno,
                "endline": endline,
                "attributes": sorted(attributes),
            }
        )

    def calculate_lcom(self) -> tuple[int, int, int]:
        """
        Calculate P, Q and LCOM.
        """

        method_count = len(self.methods)

        if method_count < 2:
            return 0, 0, 0

        p = 0
        q = 0

        for index, first_method in enumerate(
                self.methods
        ):

            first_attributes = set(
                first_method["attributes"]
            )

            for second_method in self.methods[
                                 index + 1:
                                 ]:

                second_attributes = set(
                    second_method["attributes"]
                )

                if first_attributes.intersection(
                        second_attributes
                ):
                    q += 1
                else:
                    p += 1

        lcom = max(
            p - q,
            0,
        )

        return p, q, lcom


# AST visitor
class _LCOMVisitor(ast.NodeVisitor):

    def __init__(self):
        self.classes = []

        self._class_stack = []

    @property
    def current_class(self):

        if not self._class_stack:
            return None

        return self._class_stack[-1]

    # Class
    def visit_ClassDef(self, node):

        context = _LCOMClassContext(
            name=node.name,
            lineno=node.lineno,
            endline=getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
        )

        self._class_stack.append(context)

        for statement in node.body:
            self.visit(statement)

        self._class_stack.pop()

        p, q, lcom = (
            context.calculate_lcom()
        )

        self.classes.append(
            {
                "name": context.name,
                "lcom": lcom,
                "p": p,
                "q": q,
                "method_count": len(
                    context.methods
                ),
                "methods": context.methods,
                "lineno": context.lineno,
                "endline": context.endline,
            }
        )

    # Methods
    def visit_FunctionDef(self, node):

        if self.current_class is None:
            return

        attributes = (
            self._collect_instance_attributes(
                node
            )
        )

        self.current_class.add_method(
            name=node.name,
            lineno=node.lineno,
            endline=getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
            attributes=attributes,
        )

    def visit_AsyncFunctionDef(self, node):

        self.visit_FunctionDef(node)

    # Attribute extraction
    @staticmethod
    def _collect_instance_attributes(
            method_node,
    ) -> set[str]:

        attributes = set()

        for node in ast.walk(method_node):

            if not isinstance(
                    node,
                    ast.Attribute,
            ):
                continue

            if not isinstance(
                    node.value,
                    ast.Name,
            ):
                continue

            if node.value.id != "self":
                continue

            attributes.add(node.attr)

        return attributes
