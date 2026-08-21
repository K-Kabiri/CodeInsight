import ast
from pathlib import Path

from .base import BaseMetricEngine


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_docstring(node) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_placeholder(node) -> bool:
    if isinstance(node, ast.Pass):
        return True

    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and node.value.value is Ellipsis
    )


def _block_bodies(statement) -> list[list[ast.stmt]]:
    """
    The bodies a block statement opens (each visited one nesting
    level deeper). `else`/`elif`/`except`/`finally`/`case` branches
    are indented blocks of their construct, so they count too.
    """
    if isinstance(
            statement,
            (ast.If, ast.For, ast.AsyncFor, ast.While),
    ):
        return [
            statement.body,
            statement.orelse,
        ]

    if isinstance(statement, ast.Try):
        bodies = [
            statement.body,
            statement.orelse,
            statement.finalbody,
        ]

        bodies.extend(
            handler.body
            for handler in statement.handlers
        )

        return bodies

    if isinstance(
            statement,
            (ast.With, ast.AsyncWith),
    ):
        return [statement.body]

    if isinstance(statement, ast.Match):
        return [
            case.body
            for case in statement.cases
        ]

    return []


def _is_common_constant(value) -> bool:
    """
    The exclusion list of the Magic Number rule: 0, 1, -1, 100 and
    powers of ten (and their float forms) are structural enough to
    be self-explanatory.
    """
    if isinstance(value, bool):
        return True

    if isinstance(value, int):
        return value in (0, 1, -1, 100) or (
            value != 0 and abs(value) in {
                10 ** power for power in range(1, 7)
            }
        )

    if isinstance(value, float):
        return value in (0.0, 1.0, -1.0, 100.0) or any(
            abs(value) == 10.0 ** power
            for power in range(-6, 7)
        )

    return False


class CodeSmellsEngine(BaseMetricEngine):
    """
    Code Smells: 8 curated structural smells detected via the
    standard-library `ast` (per the research note in
    `docs/code-smells.md`, each rule documented against Clean Code /
    an official reference).

    Rules and thresholds (configurable constants):

      - long-method          body > MAX_METHOD_LINES (30) lines
      - large-class          body > MAX_CLASS_LINES (200) lines
                             OR > MAX_CLASS_METHODS (15) methods
      - deep-nesting         max nesting depth > MAX_NESTING_DEPTH (4)
      - long-parameter-list  > MAX_PARAMETERS (5) parameters
      - data-class           >= MIN_DATA_CLASS_FIELDS (3) fields
                             and no (non-dunder) methods
      - magic-number         any bare numeric literal not in the
                             common-constants exclusion list
      - bare-except          `except:` with no exception type
      - empty-block          a block whose body is only placeholders
                             (`pass` / `...`), optionally preceded by
                             a docstring

    Deep-nesting depth convention (pinned in the note): the function
    body counts as level 1, a control construct directly inside it is
    level 2, and each further nested construct adds one level; the
    rule fires when the deepest construct exceeds level 4.

    Scope/completeness (ADR-0001): applicable at any Scope; every
    parsed file reports `completeness: full`. A file that fails to
    parse is reported with `completeness: partial` at file level and
    a reason — its counts are never fabricated.
    """

    MAX_METHOD_LINES = 30
    MAX_CLASS_LINES = 200
    MAX_CLASS_METHODS = 15
    MAX_NESTING_DEPTH = 4
    MAX_PARAMETERS = 5
    MIN_DATA_CLASS_FIELDS = 3

    def __init__(
            self,
            *,
            max_method_lines: int = MAX_METHOD_LINES,
            max_class_lines: int = MAX_CLASS_LINES,
            max_class_methods: int = MAX_CLASS_METHODS,
            max_nesting_depth: int = MAX_NESTING_DEPTH,
            max_parameters: int = MAX_PARAMETERS,
            min_data_class_fields: int = MIN_DATA_CLASS_FIELDS,
    ):
        self.max_method_lines = max_method_lines
        self.max_class_lines = max_class_lines
        self.max_class_methods = max_class_methods
        self.max_nesting_depth = max_nesting_depth
        self.max_parameters = max_parameters
        self.min_data_class_fields = min_data_class_fields

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> int:
        detail = self.calculate_detailed(
            python_files,
            scope,
        )

        return detail["totals"]["smells"]

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:
        files = []
        failed_files = []

        for file_path in python_files:
            result = self._analyze_file(file_path)

            files.append(result)

            if not result["parsed"]:
                failed_files.append(str(file_path))

        by_type = {}

        for result in files:
            for smell in result["smells"]:
                by_type[smell["type"]] = (
                    by_type.get(smell["type"], 0) + 1
                )

        completeness = (
            "partial"
            if failed_files
            else "full"
        )

        detail = {
            "metric": "CODE_SMELLS",
            "scope": scope,
            "completeness": completeness,
            "totals": {
                "smells": sum(by_type.values()),
                "files": len(files),
                "types": len(by_type),
            },
            "by_type": dict(sorted(by_type.items())),
            "files": files,
        }

        if failed_files:
            detail["reason"] = (
                "The following files could not be parsed and were "
                f"excluded: {', '.join(failed_files)}"
            )

        return detail

    # ---- Per-file analysis ----

    def _analyze_file(
            self,
            file_path: Path,
    ) -> dict:
        source_code = file_path.read_text(encoding="utf-8")

        try:
            tree = ast.parse(
                source_code,
                filename=str(file_path),
            )
        except SyntaxError as exc:
            return {
                "file": str(file_path),
                "parsed": False,
                "reason": f"Syntax error: {exc.msg}",
                "smells": [],
            }

        smells = []

        for node in ast.walk(tree):
            if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                smells.extend(self._long_method(node))
                smells.extend(self._deep_nesting(node))
                smells.extend(self._long_parameter_list(node))

            if isinstance(node, ast.ClassDef):
                smells.extend(self._large_class(node))
                smells.extend(self._data_class(node))

            if isinstance(node, ast.ExceptHandler):
                smells.extend(self._bare_except(node))

        smells.extend(self._empty_blocks(tree))
        smells.extend(self._magic_numbers(tree))

        return {
            "file": str(file_path),
            "parsed": True,
            "smells": smells,
        }

    # ---- Rules ----

    def _long_method(
            self,
            node,
    ) -> list[dict]:
        statements = self._body_statements(node)

        if not statements:
            return []

        start = statements[0].lineno
        end = statements[-1].end_lineno
        lines = end - start + 1

        if lines <= self.max_method_lines:
            return []

        return [
            self._smell(
                "long-method",
                node,
                (
                    f"Function body is {lines} lines "
                    f"(max {self.max_method_lines})"
                ),
            )
        ]

    def _large_class(
            self,
            node,
    ) -> list[dict]:
        statements = self._body_statements(node)

        lines = (
            statements[-1].end_lineno
            - statements[0].lineno
            + 1
            if statements
            else 1
        )

        methods = sum(
            1
            for statement in node.body
            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        )

        reasons = []

        if lines > self.max_class_lines:
            reasons.append(
                f"Class body is {lines} lines "
                f"(max {self.max_class_lines})"
            )

        if methods > self.max_class_methods:
            reasons.append(
                f"Class defines {methods} methods "
                f"(max {self.max_class_methods})"
            )

        if not reasons:
            return []

        return [
            self._smell(
                "large-class",
                node,
                "; ".join(reasons),
            )
        ]

    def _deep_nesting(
            self,
            node,
    ) -> list[dict]:
        max_level = 1

        def walk(statements, level):
            nonlocal max_level

            for statement in statements:
                bodies = _block_bodies(statement)

                if not bodies:
                    continue

                max_level = max(max_level, level)

                for body in bodies:
                    walk(body, level + 1)

        # Statements directly in the function body are at level 2
        # (the body itself is level 1).
        walk(node.body, 2)

        if max_level <= self.max_nesting_depth:
            return []

        return [
            self._smell(
                "deep-nesting",
                node,
                (
                    f"Maximum nesting depth {max_level} exceeds "
                    f"{self.max_nesting_depth}"
                ),
            )
        ]

    def _long_parameter_list(
            self,
            node,
    ) -> list[dict]:
        parameters = (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        )

        if (
                parameters
                and parameters[0].arg in ("self", "cls")
        ):
            parameters = parameters[1:]

        if len(parameters) <= self.max_parameters:
            return []

        return [
            self._smell(
                "long-parameter-list",
                node,
                (
                    f"Function takes {len(parameters)} parameters "
                    f"(max {self.max_parameters})"
                ),
            )
        ]

    def _data_class(
            self,
            node,
    ) -> list[dict]:
        methods = [
            statement
            for statement in node.body
            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
            and not _is_dunder(statement.name)
        ]

        fields = set()

        for statement in node.body:
            if isinstance(statement, ast.Assign) and not isinstance(
                    statement.value,
                    ast.Lambda,
            ):
                for target in statement.targets:
                    self._collect_data_field(
                        target,
                        fields,
                    )

            elif isinstance(statement, ast.AnnAssign):
                if statement.value is not None and not isinstance(
                        statement.value,
                        ast.Lambda,
                ):
                    self._collect_data_field(
                        statement.target,
                        fields,
                    )

        init = next(
            (
                statement
                for statement in node.body
                if isinstance(statement, ast.FunctionDef)
                and statement.name == "__init__"
            ),
            None,
        )

        if init is not None:
            for statement in ast.walk(init):
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        self._collect_instance_field(
                            target,
                            fields,
                        )

                elif isinstance(statement, ast.AnnAssign):
                    self._collect_instance_field(
                        statement.target,
                        fields,
                    )

        if (
                len(fields) < self.min_data_class_fields
                or methods
        ):
            return []

        return [
            self._smell(
                "data-class",
                node,
                (
                    f"Data class: {len(fields)} fields "
                    f"(>= {self.min_data_class_fields}) and "
                    "no methods"
                ),
            )
        ]

    def _bare_except(
            self,
            handler,
    ) -> list[dict]:
        if handler.type is not None:
            return []

        return [
            self._smell(
                "bare-except",
                handler,
                "Bare except catches every exception",
            )
        ]

    def _magic_numbers(
            self,
            tree,
    ) -> list[dict]:
        smells = []

        visitor = _MagicNumberVisitor(
            self._smell,
        )

        visitor.visit(tree)

        return visitor.smells

    def _empty_blocks(
            self,
            tree,
    ) -> list[dict]:
        smells = []

        for node in ast.walk(tree):
            bodies = []

            if isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.ClassDef,
                        ast.If,
                        ast.For,
                        ast.AsyncFor,
                        ast.While,
                        ast.With,
                        ast.AsyncWith,
                    ),
            ):
                bodies.append(node.body)

                if isinstance(
                        node,
                        (ast.If, ast.For, ast.AsyncFor, ast.While),
                ):
                    bodies.append(node.orelse)

            elif isinstance(node, ast.Try):
                bodies.append(node.body)
                bodies.append(node.orelse)
                bodies.append(node.finalbody)
                bodies.extend(
                    handler.body
                    for handler in node.handlers
                )

            elif isinstance(node, ast.Match):
                bodies.extend(
                    case.body
                    for case in node.cases
                )

            for body in bodies:
                if self._is_empty(body):
                    smells.append(
                        self._smell(
                            "empty-block",
                            node,
                            (
                                "Empty block: body contains only "
                                "placeholder statements"
                            ),
                        )
                    )

        return smells

    # ---- Helpers ----

    def _body_statements(
            self,
            node,
    ) -> list[ast.stmt]:
        statements = list(node.body)

        if statements and _is_docstring(statements[0]):
            statements = statements[1:]

        return statements

    @staticmethod
    def _is_empty(body: list[ast.stmt]) -> bool:
        # An empty list means the branch does not exist (e.g. an
        # `if` without `else`); only a real block can be empty.
        if not body:
            return False

        return all(
            _is_docstring(statement)
            or _is_placeholder(statement)
            for statement in body
        )

    def _collect_data_field(
            self,
            target,
            fields: set,
    ) -> None:
        if (
                isinstance(target, ast.Name)
                and not _is_dunder(target.id)
        ):
            fields.add(target.id)

    def _collect_instance_field(
            self,
            target,
            fields: set,
    ) -> None:
        if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
        ):
            fields.add(target.attr)

    @staticmethod
    def _smell(
            smell_type: str,
            node,
            message: str,
    ) -> dict:
        return {
            "type": smell_type,
            "lineno": node.lineno,
            "endline": getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
            "message": message,
        }


class _MagicNumberVisitor(ast.NodeVisitor):
    """
    Finds bare numeric literals, excluding the common-constants list
    and structural positions (function-definition defaults and
    arguments of dunder calls such as `super().__init__()`).
    """

    def __init__(
            self,
            smell_factory,
    ):
        self.smell_factory = smell_factory

        self._parent = None

        self.smells = []

    def visit_Constant(self, node):
        value = node.value

        if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
        ):
            return

        if _is_common_constant(value):
            return

        if self._is_structural(node):
            return

        self.smells.append(
            self.smell_factory(
                "magic-number",
                node,
                (
                    f"Magic number {value!r} — "
                    "use a named constant"
                ),
            )
        )

    def _is_structural(self, node) -> bool:
        parent = self._parent

        if parent is None:
            return False

        # Default value of a function definition:
        #   def f(n=42): ...
        if isinstance(parent, ast.arg):
            return parent.default is node

        # Positional/keyword default directly on `arguments`.
        if isinstance(parent, ast.arguments):
            return True

        # Argument of a dunder call:
        #   super().__init__(42)
        if isinstance(parent, ast.Call):
            func = parent.func

            if (
                    isinstance(func, ast.Attribute)
                    and _is_dunder(func.attr)
            ):
                return node in parent.args or any(
                    keyword.value is node
                    for keyword in parent.keywords
                )

        return False

    def generic_visit(self, node):
        previous_parent = self._parent

        self._parent = node

        super().generic_visit(node)

        self._parent = previous_parent
