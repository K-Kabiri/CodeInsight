import ast
from pathlib import Path

from .base import BaseMetricEngine


class CognitiveComplexityEngine(BaseMetricEngine):
    """
    Cognitive Complexity engine for Python.

    Based on the Cognitive Complexity model introduced by
    SonarSource.

    The implementation follows the main concepts of the
    Cognitive Complexity model:

    - Structural increments:
        if
        elif
        else
        loops
        except
        match
        conditional expressions

    - Nesting increments:
        Structural increments become more expensive when
        they appear inside nested control-flow structures.

    - Fundamental increments:
        break
        continue
        recursion

    - Logical sequences:
        A sequence of binary logical operators contributes
        one point for each logical sequence.

    Complexity is calculated independently for each function
    or method and then aggregated at file/project level.

    Detailed contributions are preserved so that the reporting
    and AI layers can explain how the final score was produced.
    """

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> int:
        return self.calculate_detailed(
            python_files,
            scope,
        )["total"]

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:

        files = []
        all_function_scores = []

        for file_path in python_files:
            result = self._analyze_file(file_path)

            files.append(result)

            all_function_scores.extend(
                function["complexity"]
                for function in result["functions"]
            )

        total = sum(all_function_scores)

        average = (
            total / len(all_function_scores)
            if all_function_scores
            else 0.0
        )

        return {
            "metric": "Cognitive Complexity",
            "total": total,
            "average": average,
            "function_count": len(all_function_scores),
            "files": files,
        }

    @staticmethod
    def _analyze_file(file_path: Path) -> dict:

        source_code = file_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source_code,
            filename=str(file_path),
        )

        visitor = _CognitiveComplexityVisitor()
        visitor.visit(tree)

        total = sum(
            function["complexity"]
            for function in visitor.functions
        )

        return {
            "file": str(file_path),
            "total": total,
            "functions": visitor.functions,
        }


class _FunctionContext:

    def __init__(
            self,
            name: str,
            lineno: int,
            endline: int,
            is_method: bool = False,
            classname: str | None = None,
    ):
        self.name = name
        self.lineno = lineno
        self.endline = endline

        self.is_method = is_method
        self.classname = classname

        self.complexity = 0

        self.nesting = 0
        self.max_nesting = 0

        self.contributions = []

    def add(
            self,
            node: ast.AST,
            amount: int,
            kind: str,
            reason: str,
    ):
        self.complexity += amount

        self.contributions.append(
            {
                "type": kind,
                "increment": amount,
                "nesting": self.nesting,
                "lineno": getattr(
                    node,
                    "lineno",
                    None,
                ),
                "reason": reason,
            }
        )

    def enter_nesting(self):
        self.nesting += 1

        self.max_nesting = max(
            self.max_nesting,
            self.nesting,
        )

    def leave_nesting(self):
        self.nesting -= 1


class _CognitiveComplexityVisitor(ast.NodeVisitor):

    def __init__(self):
        self.functions = []

        self._function_stack = []
        self._class_stack = []

    # Context
    @property
    def current_function(self):
        if not self._function_stack:
            return None

        return self._function_stack[-1]

    @property
    def current_class(self):
        if not self._class_stack:
            return None

        return self._class_stack[-1]

    def _create_function_context(self, node):

        return _FunctionContext(
            name=node.name,
            lineno=node.lineno,
            endline=getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
            is_method=self.current_class is not None,
            classname=self.current_class,
        )

    def _finish_function(self, context):

        result = {
            "name": context.name,
            "type": (
                "method"
                if context.is_method
                else "function"
            ),
            "complexity": context.complexity,
            "max_nesting": context.max_nesting,
            "lineno": context.lineno,
            "endline": context.endline,
            "contributions": context.contributions,
        }

        if context.classname is not None:
            result["classname"] = context.classname

        self.functions.append(result)

    # Functions
    def visit_FunctionDef(self, node):

        context = self._create_function_context(node)

        self._function_stack.append(context)

        for statement in node.body:
            self.visit(statement)

        self._function_stack.pop()

        self._finish_function(context)

    def visit_AsyncFunctionDef(self, node):

        context = self._create_function_context(node)

        self._function_stack.append(context)

        for statement in node.body:
            self.visit(statement)

        self._function_stack.pop()

        self._finish_function(context)

    # Classes
    def visit_ClassDef(self, node):

        self._class_stack.append(node.name)

        for statement in node.body:
            self.visit(statement)

        self._class_stack.pop()

    # Structural increment
    def _add_structural(
            self,
            node,
            kind: str,
            reason: str,
    ):

        context = self.current_function

        if context is None:
            return

        amount = 1 + context.nesting

        context.add(
            node=node,
            amount=amount,
            kind=kind,
            reason=reason,
        )

    # IF
    def visit_If(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        self._add_structural(
            node,
            kind="if",
            reason="break in linear flow",
        )

        self.visit(node.test)

        context.enter_nesting()

        for statement in node.body:
            self.visit(statement)

        context.leave_nesting()

        if node.orelse:

            if (
                    len(node.orelse) == 1
                    and isinstance(
                node.orelse[0],
                ast.If,
            )
            ):
                self._visit_elif(node.orelse[0])

            else:
                self._visit_else(node.orelse)

    # ELIF
    def _visit_elif(self, node):

        context = self.current_function

        if context is None:
            return

        context.add(
            node=node,
            # Same formula as `if`: 1 + current_nesting_level. At this
            # point the `if` body's nesting has been left, so the
            # nesting level is the construct's own — a nested elif
            # must not collapse to a flat +1 (docs/cognitive_complexity.md).
            amount=1 + context.nesting,
            kind="elif",
            reason="break in linear flow",
        )

        self.visit(node.test)

        context.enter_nesting()

        for statement in node.body:
            self.visit(statement)

        context.leave_nesting()

        if node.orelse:

            if (
                    len(node.orelse) == 1
                    and isinstance(
                node.orelse[0],
                ast.If,
            )
            ):
                self._visit_elif(node.orelse[0])

            else:
                self._visit_else(node.orelse)

    # ELSE
    def _visit_else(self, statements):

        context = self.current_function

        if context is None:
            return

        first_node = statements[0]

        context.add(
            node=first_node,
            # Same formula as `if`/`elif`: 1 + current_nesting_level
            # (docs/cognitive_complexity.md).
            amount=1 + context.nesting,
            kind="else",
            reason="break in linear flow",
        )

        for statement in statements:
            self.visit(statement)

    # FOR
    def visit_For(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        self._add_structural(
            node,
            kind="for",
            reason="loop structure",
        )

        self.visit(node.iter)

        context.enter_nesting()

        for statement in node.body:
            self.visit(statement)

        context.leave_nesting()

        for statement in node.orelse:
            self.visit(statement)

    # ASYNC FOR
    def visit_AsyncFor(self, node):
        self.visit_For(node)

    # WHILE
    def visit_While(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        self._add_structural(
            node,
            kind="while",
            reason="loop structure",
        )

        self.visit(node.test)

        context.enter_nesting()

        for statement in node.body:
            self.visit(statement)

        context.leave_nesting()

        for statement in node.orelse:
            self.visit(statement)

    # TRY
    def visit_Try(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        for statement in node.body:
            self.visit(statement)

        for handler in node.handlers:
            self.visit(handler)

        for statement in node.orelse:
            self.visit(statement)

        for statement in node.finalbody:
            self.visit(statement)

    # EXCEPT
    def visit_ExceptHandler(self, node):

        context = self.current_function

        if context is None:
            return

        self._add_structural(
            node,
            kind="except",
            reason="exception handling branch",
        )

        context.enter_nesting()

        for statement in node.body:
            self.visit(statement)

        context.leave_nesting()


    # TERNARY
    def visit_IfExp(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        context.add(
            node=node,
            amount=1,
            kind="conditional_expression",
            reason="ternary conditional",
        )

        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    # BOOLEAN EXPRESSIONS
    def visit_BoolOp(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        context.add(
            node=node,
            amount=1,
            kind="boolean_sequence",
            reason="sequence of binary logical operators",
        )

        for value in node.values:
            self.visit(value)

    # BREAK
    def visit_Break(self, node):

        context = self.current_function

        if context is None:
            return

        context.add(
            node=node,
            amount=1,
            kind="break",
            reason="break in linear flow",
        )

    # CONTINUE
    def visit_Continue(self, node):

        context = self.current_function

        if context is None:
            return

        context.add(
            node=node,
            amount=1,
            kind="continue",
            reason="break in linear flow",
        )

    # MATCH
    def visit_Match(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        self._add_structural(
            node,
            kind="match",
            reason="multi-way branching",
        )

        self.visit(node.subject)

        context.enter_nesting()

        for case in node.cases:
            self._visit_match_case(case)

        context.leave_nesting()

    def _visit_match_case(self, case):

        context = self.current_function

        if context is None:
            return

        if case.guard is not None:

            self._add_structural(
                case.guard,
                kind="match_guard",
                reason="conditional match guard",
            )

            self.visit(case.guard)

        for statement in case.body:
            self.visit(statement)

    # RECURSION
    def visit_Call(self, node):

        context = self.current_function

        if context is None:
            self.generic_visit(node)
            return

        if self._is_recursive_call(
                node,
                context,
        ):
            context.add(
                node=node,
                amount=1,
                kind="recursion",
                reason="recursive call",
            )

        self.generic_visit(node)

    @staticmethod
    def _is_recursive_call(
            node,
            context,
    ) -> bool:

        if not isinstance(
                node.func,
                ast.Name,
        ):
            return False

        return node.func.id == context.name