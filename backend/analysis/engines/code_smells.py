import ast
import io
import textwrap
import tokenize
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


class _Located:
    """
    Minimal stand-in for an AST node that carries only a line range,
    used for findings that have no AST node of their own (commented
    out code blocks).
    """

    def __init__(self, lineno: int, end_lineno: int | None = None):
        self.lineno = lineno
        self.end_lineno = (
            end_lineno
            if end_lineno is not None
            else lineno
        )


class CodeSmellsEngine(BaseMetricEngine):
    """
    Code Smells: 10 curated structural smells detected via the
    standard-library `ast` (and `tokenize` for the comment-based
    rule) per the research note in `docs/code-smells.md` — each rule
    documented against Clean Code / an official reference.

    Rules and thresholds (configurable constants):

      - long-method          body > MAX_METHOD_LINES (30) lines
      - large-class          body > MAX_CLASS_LINES (200) lines
                             OR > MAX_CLASS_METHODS (15) methods
      - deep-nesting         max nesting depth > MAX_NESTING_DEPTH (4)
      - long-parameter-list  > MAX_PARAMETERS (5) parameters
      - data-class           >= MIN_DATA_CLASS_FIELDS (3) fields
                             and no (non-dunder) methods
      - bare-except          `except:` with no exception type
      - empty-block          a block whose body is only placeholders
                             (`pass` / `...`), optionally preceded by
                             a docstring
      - searchable-names     a single-letter local variable or
                             parameter (i/j/k/x/y/z/e/_ excluded)
      - commented-out-code   comment text that parses as valid Python
                             and carries code-like syntax
      - dead-function        a function/method whose name is never
                             referenced in the analyzed file set

    Deep-nesting depth convention (pinned in the note): the function
    body counts as level 1, a control construct directly inside it is
    level 2, and each further nested construct adds one level; the
    rule fires when the deepest construct exceeds level 4.

    Every finding carries the explainable-detail entity fields:
    `entity` (the function/method/class/identifier the finding
    attaches to, or null), `entity_type` (function/method/class/
    variable/parameter/except/block/…), and `class_name` (the
    containing class for methods). Existing `type`/`lineno`/
    `endline`/`message` fields are unchanged.

    Scope/completeness (ADR-0001): applicable at any Scope; every
    parsed file reports `completeness: full`. A file that fails to
    parse is reported with `completeness: partial` at file level and
    a reason — its counts are never fabricated. The dead-function
    rule is whole-analyzed-file-set by nature: at `single_file`
    scope a function may be used by files outside the analysis, so
    its findings are a best-effort signal of that scope (documented
    in `docs/code-smells.md`), never a claim about unanalyzed files.
    """

    MAX_METHOD_LINES = 30
    MAX_CLASS_LINES = 200
    MAX_CLASS_METHODS = 15
    MAX_NESTING_DEPTH = 4
    MAX_PARAMETERS = 5
    MIN_DATA_CLASS_FIELDS = 3
    SINGLE_LETTER_EXCEPTIONS = frozenset(
        {"i", "j", "k", "x", "y", "z", "e", "_"}
    )

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

        referenced_names = self._collect_references(python_files)

        for file_path in python_files:
            result = self._analyze_file(
                file_path,
                referenced_names,
            )

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

    # ---- Cross-file reference collection ----

    def _collect_references(
            self,
            python_files: list[Path],
    ) -> set[str]:
        """
        Every name referenced anywhere in the analyzed file set:
        `Name` ids (calls, callbacks, imports, entry points) and
        `Attribute` attrs (`self.run()`, `Service.run()`). Used by
        the dead-function rule. Definition-site names are not `Name`
        nodes, so a definition alone never counts as a reference.
        """
        references = set()

        for file_path in python_files:
            try:
                tree = ast.parse(
                    file_path.read_text(encoding="utf-8"),
                    filename=str(file_path),
                )
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    references.add(node.id)
                elif isinstance(node, ast.Attribute):
                    references.add(node.attr)

        return references

    # ---- Per-file analysis ----

    def _analyze_file(
            self,
            file_path: Path,
            referenced_names: set[str] | None = None,
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

        self._parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
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
                smells.extend(self._searchable_names(node))
                smells.extend(
                    self._dead_function(
                        node,
                        referenced_names,
                    )
                )

            if isinstance(node, ast.ClassDef):
                smells.extend(self._large_class(node))
                smells.extend(self._data_class(node))

            if isinstance(node, ast.ExceptHandler):
                smells.extend(self._bare_except(node))

        smells.extend(self._empty_blocks(tree))
        smells.extend(self._commented_out_code(tree, source_code))

        return {
            "file": str(file_path),
            "parsed": True,
            "smells": smells,
        }

    # ---- Entity resolution ----

    def _function_entity(
            self,
            node,
    ) -> tuple[str, str, str | None]:
        """
        Entity fields for a function/method node: a function defined
        directly in a class body is a method (with its containing
        class); anything else — module-level and nested functions —
        is a plain function.
        """
        parent = self._parents.get(node)

        if isinstance(parent, ast.ClassDef):
            return (node.name, "method", parent.name)

        return (node.name, "function", None)

    def _enclosing_entity(
            self,
            node,
    ) -> tuple[str | None, str | None, str | None]:
        """
        The nearest named entity enclosing a node (including the
        node itself when it is a function or class): the nearest
        function/method, else the nearest class, else (None, None,
        None).
        """
        current = node

        while current is not None:
            if isinstance(
                    current,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                return self._function_entity(current)

            if isinstance(current, ast.ClassDef):
                return (current.name, "class", None)

            current = self._parents.get(current)

        return (None, None, None)

    def _enclosing_entity_for_line(
            self,
            lineno: int,
            tree,
    ) -> tuple[str | None, str | None, str | None]:
        """
        The deepest function/class whose line range contains the
        given line — used for findings that have no AST node of
        their own (commented-out code).
        """
        enclosing = None

        for node in ast.walk(tree):
            if not isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.ClassDef,
                    ),
            ):
                continue

            end = getattr(node, "end_lineno", node.lineno)

            if node.lineno <= lineno <= end:
                if (
                        enclosing is None
                        or node.lineno > enclosing.lineno
                ):
                    enclosing = node

        if enclosing is None:
            return (None, None, None)

        if isinstance(
                enclosing,
                (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            return self._function_entity(enclosing)

        return (enclosing.name, "class", None)

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

        entity, entity_type, class_name = self._function_entity(node)

        return [
            self._smell(
                "long-method",
                node,
                (
                    f"Function body is {lines} lines "
                    f"(max {self.max_method_lines})"
                ),
                entity=entity,
                entity_type=entity_type,
                class_name=class_name,
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
                entity=node.name,
                entity_type="class",
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

        entity, entity_type, class_name = self._function_entity(node)

        return [
            self._smell(
                "deep-nesting",
                node,
                (
                    f"Maximum nesting depth {max_level} exceeds "
                    f"{self.max_nesting_depth}"
                ),
                entity=entity,
                entity_type=entity_type,
                class_name=class_name,
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

        entity, entity_type, class_name = self._function_entity(node)

        return [
            self._smell(
                "long-parameter-list",
                node,
                (
                    f"Function takes {len(parameters)} parameters "
                    f"(max {self.max_parameters})"
                ),
                entity=entity,
                entity_type=entity_type,
                class_name=class_name,
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
                entity=node.name,
                entity_type="class",
            )
        ]

    def _bare_except(
            self,
            handler,
    ) -> list[dict]:
        if handler.type is not None:
            return []

        entity, entity_type, class_name = self._enclosing_entity(
            handler,
        )

        if entity is None:
            entity_type = "except"

        return [
            self._smell(
                "bare-except",
                handler,
                "Bare except catches every exception",
                entity=entity,
                entity_type=entity_type,
                class_name=class_name,
            )
        ]

    def _searchable_names(
            self,
            node,
    ) -> list[dict]:
        """
        Searchable Names: single-letter local variables and
        parameters are hard to search for (N4). Loop counters
        (i/j/k), coordinates (x/y/z), exception names (e) and the
        throwaway `_` are excluded, matching pylint's `good-names`
        and SonarQube S117.
        """
        smells = []
        seen = set()

        def consider(
                name: str,
                entity_type: str,
                location,
        ) -> None:
            if (
                    name in seen
                    or len(name) != 1
                    or name in self.SINGLE_LETTER_EXCEPTIONS
                    or _is_dunder(name)
            ):
                return

            seen.add(name)

            smells.append(
                self._smell(
                    "searchable-names",
                    location,
                    (
                        f"Single-letter {entity_type} name {name!r} "
                        "is hard to search"
                    ),
                    entity=name,
                    entity_type=entity_type,
                )
            )

        arguments = node.args

        parameters = (
            list(arguments.posonlyargs)
            + list(arguments.args)
            + list(arguments.kwonlyargs)
        )

        if arguments.vararg is not None:
            parameters.append(arguments.vararg)

        if arguments.kwarg is not None:
            parameters.append(arguments.kwarg)

        for parameter in parameters:
            consider(
                parameter.arg,
                "parameter",
                parameter,
            )

        # Local variables: store-target names and exception-handler
        # names in this function's scope, minus the bindings of
        # nested scopes.
        local_names = self._scope_bindings(node)

        for nested in ast.walk(node):
            if nested is node:
                continue

            if isinstance(
                    nested,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                for name in self._scope_bindings(nested):
                    local_names.pop(name, None)

        for name, location in local_names.items():
            consider(
                name,
                "variable",
                location,
            )

        return smells

    @staticmethod
    def _scope_bindings(subtree) -> dict[str, object]:
        """
        The names bound in one scope: store-target `Name`s (plain
        assignments, loop targets, `with` targets, comprehensions,
        walrus) and `except ... as` handler names. Keyed by name
        with the first binding node as value.
        """
        bindings = {}

        for child in ast.walk(subtree):
            if (
                    isinstance(child, ast.Name)
                    and isinstance(child.ctx, ast.Store)
            ):
                bindings.setdefault(child.id, child)

            elif (
                    isinstance(child, ast.ExceptHandler)
                    and child.name
            ):
                bindings.setdefault(child.name, child)

        return bindings

    def _commented_out_code(
            self,
            tree,
            source_code: str,
    ) -> list[dict]:
        """
        Commented-Out Code: a run of consecutive comment lines whose
        content parses as valid Python and carries a code-like
        syntax signal (assignment, call, bracket, structural
        keyword) — per SonarQube S125. Directives (`#!`, `-*-`,
        `# type:`, `# noqa`, tool pragmas) are never flagged.
        """
        smells = []
        comment_lines = []

        try:
            tokens = tokenize.generate_tokens(
                io.StringIO(source_code).readline,
            )

            for token in tokens:
                if token.type == tokenize.COMMENT:
                    comment_lines.append(
                        (token.start[0], token.string)
                    )
        except (tokenize.TokenError, IndentationError):
            return smells

        groups = []
        current = []
        previous = None

        for lineno, text in comment_lines:
            if previous is not None and lineno == previous + 1:
                current.append((lineno, text))
            else:
                if current:
                    groups.append(current)

                current = [(lineno, text)]

            previous = lineno

        if current:
            groups.append(current)

        for group in groups:
            lines = []

            for lineno, text in group:
                # Remove the comment marker and the single space
                # that usually follows it, preserving the relative
                # indentation that commented-out code keeps.
                content = text.lstrip("#")

                if content.startswith(" "):
                    content = content[1:]

                stripped = content.rstrip()

                if (
                        not stripped
                        or self._is_comment_directive(stripped)
                ):
                    continue

                lines.append(stripped)

            if not lines:
                continue

            if not any(
                    self._looks_like_code(line)
                    for line in lines
            ):
                continue

            candidate = textwrap.dedent("\n".join(lines))

            try:
                compile(
                    candidate,
                    "<commented-out-code>",
                    "exec",
                )
            except SyntaxError:
                continue

            entity, entity_type, class_name = (
                self._enclosing_entity_for_line(
                    group[0][0],
                    tree,
                )
            )

            smells.append(
                self._smell(
                    "commented-out-code",
                    _Located(group[0][0], group[-1][0]),
                    "Commented-out code should be removed",
                    entity=entity,
                    entity_type=entity_type,
                    class_name=class_name,
                )
            )

        return smells

    def _dead_function(
            self,
            node,
            referenced_names: set[str] | None,
    ) -> list[dict]:
        """
        Dead Function: a function/method whose name is never
        referenced in the analyzed file set (F4). Dunders are
        excluded; recursion, decorators, callbacks, `self.x` /
        `ClassName.x` calls and `if __name__ == "__main__"` entry
        points all count as references.
        """
        if _is_dunder(node.name):
            return []

        if (
                referenced_names is not None
                and node.name in referenced_names
        ):
            return []

        entity, entity_type, class_name = self._function_entity(node)

        return [
            self._smell(
                "dead-function",
                node,
                f"Function {node.name!r} is never used",
                entity=entity,
                entity_type=entity_type,
                class_name=class_name,
            )
        ]

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
                    entity, entity_type, class_name = (
                        self._enclosing_entity(node)
                    )

                    if entity is None:
                        entity_type = "block"

                    smells.append(
                        self._smell(
                            "empty-block",
                            node,
                            (
                                "Empty block: body contains only "
                                "placeholder statements"
                            ),
                            entity=entity,
                            entity_type=entity_type,
                            class_name=class_name,
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

    @staticmethod
    def _is_comment_directive(text: str) -> bool:
        """
        Comment text that is a directive, never commented-out code:
        shebangs, coding declarations, type ignores and tool
        pragmas.
        """
        text = text.lstrip()
        lowered = text.lower()

        if text.startswith("!"):
            return True

        if "-*-" in text:
            return True

        if lowered.startswith("type:"):
            return True

        if lowered.startswith(
                ("noqa", "pragma:", "pylint:", "ruff:", "fmt:", "mypy:")
        ):
            return True

        return False

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        text = text.lstrip()

        structural_prefixes = (
            "def ", "class ", "import ", "from ", "return ", "for ",
            "while ", "if ", "elif ", "else:", "try:", "except ",
            "with ", "assert ", "raise ", "del ", "pass", "break",
            "continue", "yield ", "lambda ", "async ", "await ",
            "print(", "global ", "nonlocal ",
        )

        if text.startswith(structural_prefixes):
            return True

        return any(
            marker in text
            for marker in ("=", "(", "[", "{", "@", "->")
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
            *,
            entity: str | None = None,
            entity_type: str | None = None,
            class_name: str | None = None,
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
            "entity": entity,
            "entity_type": entity_type,
            "class_name": class_name,
        }
