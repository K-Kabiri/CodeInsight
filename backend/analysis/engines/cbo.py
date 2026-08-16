import ast
from pathlib import Path

from .base import BaseMetricEngine


class CBOEngine(BaseMetricEngine):
    """
    Coupling Between Object Classes (CBO).

    CBO measures the number of distinct classes to which
    a class is coupled.

    Only references to classes that are actually defined
    in the analyzed Python project are considered.

    Multiple references to the same class count as one
    coupling.
    """

    def calculate(self, python_files: list[Path]) -> int:
        result = self.calculate_detailed(python_files)

        return result["total"]

    def calculate_detailed(
            self,
            python_files: list[Path],
    ) -> dict:

        class_index = self._collect_classes(
            python_files
        )

        files = []
        all_scores = []

        for file_path in python_files:
            result = self._analyze_file(
                file_path,
                class_index,
            )

            files.append(result)

            all_scores.extend(
                item["cbo"]
                for item in result["classes"]
            )

        total = sum(all_scores)

        average = (
            total / len(all_scores)
            if all_scores
            else 0.0
        )

        return {
            "metric": "CBO",
            "total": total,
            "average": average,
            "class_count": len(all_scores),
            "files": files,
        }

    # =========================================================
    # Class discovery
    # =========================================================

    @staticmethod
    def _collect_classes(
            python_files: list[Path],
    ) -> set[str]:
        """
        Collect all class names defined in the project.
        """

        classes = set()

        for file_path in python_files:
            source_code = file_path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source_code,
                filename=str(file_path),
            )

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.add(node.name)

        return classes

    # =========================================================
    # File analysis
    # =========================================================

    @staticmethod
    def _analyze_file(
            file_path: Path,
            class_index: set[str],
    ) -> dict:

        source_code = file_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source_code,
            filename=str(file_path),
        )

        visitor = _CBOVisitor(
            class_index=class_index,
        )

        visitor.visit(tree)

        return {
            "file": str(file_path),
            "total": sum(
                item["cbo"]
                for item in visitor.classes
            ),
            "classes": visitor.classes,
        }


class _CBOContext:

    def __init__(
            self,
            name: str,
            lineno: int,
            endline: int,
    ):
        self.name = name
        self.lineno = lineno
        self.endline = endline

        self.coupled_classes: set[str] = set()

    def add_coupling(
            self,
            class_name: str,
    ) -> None:

        if class_name != self.name:
            self.coupled_classes.add(
                class_name
            )

    @property
    def cbo(self) -> int:
        return len(self.coupled_classes)


class _CBOVisitor(ast.NodeVisitor):

    def __init__(
            self,
            class_index: set[str],
    ):
        self.class_index = class_index

        self.classes = []

        self._class_stack = []

    @property
    def current_class(self):

        if not self._class_stack:
            return None

        return self._class_stack[-1]

    # =========================================================
    # Class
    # =========================================================

    def visit_ClassDef(self, node):

        context = _CBOContext(
            name=node.name,
            lineno=node.lineno,
            endline=getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
        )

        self._class_stack.append(context)

        # -----------------------------------------------------
        # Inheritance
        # -----------------------------------------------------

        for base in node.bases:
            self._check_reference(base)

        # -----------------------------------------------------
        # Decorators
        # -----------------------------------------------------

        for decorator in node.decorator_list:
            self._check_reference(decorator)

        # -----------------------------------------------------
        # Class body
        # -----------------------------------------------------

        for statement in node.body:
            self.visit(statement)

        self._class_stack.pop()

        self.classes.append(
            {
                "name": context.name,
                "cbo": context.cbo,
                "coupled_classes": sorted(
                    context.coupled_classes
                ),
                "lineno": context.lineno,
                "endline": context.endline,
            }
        )

    # =========================================================
    # Function definitions
    # =========================================================

    def visit_FunctionDef(self, node):

        if self.current_class is None:
            return self.generic_visit(node)

        # Parameters
        for argument in (
                node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
        ):
            if argument.annotation:
                self._check_reference(
                    argument.annotation
                )

        if node.args.vararg and node.args.vararg.annotation:
            self._check_reference(
                node.args.vararg.annotation
            )

        if node.args.kwarg and node.args.kwarg.annotation:
            self._check_reference(
                node.args.kwarg.annotation
            )

        # Return type
        if node.returns:
            self._check_reference(
                node.returns
            )

        # Function body
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    # =========================================================
    # Object creation
    # =========================================================

    def visit_Call(self, node):

        if self.current_class is None:
            return self.generic_visit(node)

        class_name = self._extract_class_name(
            node.func
        )

        if class_name:
            self._add_if_class(
                class_name
            )

        self.generic_visit(node)

    # =========================================================
    # Attribute access
    # =========================================================

    def visit_Attribute(self, node):

        if self.current_class is None:
            return self.generic_visit(node)

        class_name = self._extract_class_name(
            node
        )

        if class_name:
            self._add_if_class(
                class_name
            )

        self.generic_visit(node)

    # =========================================================
    # Annotations
    # =========================================================

    def visit_AnnAssign(self, node):

        if node.annotation:
            self._check_reference(
                node.annotation
            )

        self.generic_visit(node)

    # =========================================================
    # Name
    # =========================================================

    def visit_Name(self, node):

        if self.current_class is None:
            return

        self._add_if_class(node.id)

    # =========================================================
    # Reference resolution
    # =========================================================

    def _check_reference(self, node):

        class_name = self._extract_class_name(
            node
        )

        if class_name:
            self._add_if_class(
                class_name
            )

    def _add_if_class(
            self,
            class_name: str,
    ):

        if class_name in self.class_index:
            self.current_class.add_coupling(
                class_name
            )

    # =========================================================
    # AST name extraction
    # =========================================================

    @staticmethod
    def _extract_class_name(node):

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            return node.attr

        if isinstance(node, ast.Subscript):
            return _CBOVisitor._extract_class_name(
                node.value
            )

        return None