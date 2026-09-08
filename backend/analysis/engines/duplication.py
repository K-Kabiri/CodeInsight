import ast
import io
import re
import tokenize
import zlib
from collections import defaultdict
from pathlib import Path

from .base import BaseMetricEngine
from .loc import LOCEngine


# Normalized markers for the structural tokens, so that whitespace
# differences (tabs vs spaces, indent width) never break a match —
# statement structure is preserved by the presence of the markers.
_INDENT_MARKER = "<INDENT>"
_DEDENT_MARKER = "<DEDENT>"

# Human-readable labels for the AST construct a duplicated region
# resolves to. The exact physical lines stay authoritative: these
# labels are the best-effort explainability the region maps to, so
# the `kind` field (and its sibling `entity`/`entity_type`/
# `class_name`) lets the UI answer "what was repeated — a function,
# a class, a loop, an if/else — and where".
_PLAIN_STATEMENT_KINDS = {
    ast.Assign: "assignment",
    ast.AnnAssign: "assignment",
    ast.AugAssign: "assignment",
    ast.Expr: "expression",
    ast.Return: "return statement",
    ast.Raise: "raise statement",
    ast.Import: "import statement",
    ast.ImportFrom: "import statement",
    ast.Delete: "delete statement",
    ast.Assert: "assert statement",
    ast.Pass: "pass statement",
    ast.Break: "break statement",
    ast.Continue: "continue statement",
    ast.Global: "global statement",
    ast.Nonlocal: "nonlocal statement",
}


def _construct_kind(node: ast.stmt) -> str:
    """Human label of one AST statement (compound or plain).

    Async variants are checked first because they subclass their
    sync counterparts (`ast.AsyncFor` *is an* `ast.For`).
    """
    if isinstance(node, ast.AsyncFor):
        return "async for loop"

    if isinstance(node, ast.For):
        return "for loop"

    if isinstance(node, ast.AsyncWith):
        return "async with block"

    if isinstance(node, ast.With):
        return "with block"

    if isinstance(node, ast.While):
        return "while loop"

    if isinstance(node, ast.If):
        return "if/elif/else"

    if isinstance(node, ast.Try):
        return "try/except"

    if isinstance(node, ast.Match):
        return "match statement"

    for cls, label in _PLAIN_STATEMENT_KINDS.items():
        if isinstance(node, cls):
            return label

    return "statement"


def _is_named_construct(node) -> bool:
    return isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
    )


def _node_end(node) -> int:
    return getattr(node, "end_lineno", node.lineno)

# Hash parameters for the Rabin-Karp rolling hash (collisions are
# verified away by direct comparison before trusting a match).
_HASH_BASE = 911382323
_HASH_MOD = (1 << 61) - 1

_STRING_PREFIX = re.compile(r"^[rRuUbBfF]*")


def _token_hash(text: str) -> int:
    return zlib.crc32(text.encode("utf-8"))


def _strip_string_prefix(text: str) -> str:
    match = _STRING_PREFIX.match(text)

    if match is None:
        return text

    return text[match.end():]


class DuplicationEngine(BaseMetricEngine):
    """
    Duplication (SonarQube semantics, per `docs/Duplication.md`).

    Token streams are built with the standard-library `tokenize`
    module and compared across the analyzed files (project Input).
    The comparison stream keeps NAME, OP, NUMBER, STRING, keywords
    and the structural tokens NEWLINE/INDENT/DEDENT (INDENT and
    DEDENT are normalized to markers; comments, non-logical newlines
    and string prefixes are excluded, per the research note). Token
    texts are compared as-is, so only Type-1 (exact) clones are
    found by default.

    Detection: a rolling hash over windows of `MIN_TOKENS` (default
    100) groups candidate starts; each group is verified by direct
    comparison and expanded left/right to the maximal common repeat;
    a clone group is kept only when every occurrence spans at least
    `MIN_LINES` (default 10) distinct physical lines. Groups are then
    canonicalized (`_canonicalize_clones`): a group whose every
    occurrence already lies inside the occurrences of an earlier
    (longest-first) kept group is dropped — this removes the
    *rotation* artifacts of periodic files (a 72-line unit copied
    twelve times also matches at lines 49–120, 50–121, …) and nested
    inner repeats, so `duplicated_blocks` counts the maximal repeated
    sequences. Measures:

      duplicated_blocks = number of canonical clone groups
      duplicated_lines  = union of physical lines in duplicated
                          blocks (each line counted once per file)
      duplicated_tokens = tokens lying inside duplicated blocks
      Duplication     = duplicated_lines / lines_of_code * 100,
                          where lines_of_code is the physical-line
                          count over the successfully tokenized
                          files (Radon `loc`) — the SonarQube
                          formula's `lines` denominator, which keeps
                          the ratio in [0, 100] even when duplicated
                          regions cover comment/blank lines

    Explainable findings: each occurrence in `blocks` is enriched
    from the file's AST so the UI (and the AI prompt) can say *what*
    was repeated and *where*: `group`/`ordinal`/`copies` tie the
    occurrences of one clone group together (which copies are
    duplicates of each other), and `entity`/`entity_type`/
    `class_name`/`kind` name the nearest containing function/class
    (or "module") plus the construct the region itself is — a whole
    function/method/class, a single statement like a for/while/if-
    elif-else block, or a `statements` sequence. Region lines are
    token boundaries and the construct labels are best-effort: the
    exact `start_line`/`end_line` are always authoritative.

    Scope/completeness (ADR-0001): the metric runs at any scope and
    never assumes code outside the analyzed input. On `project`
    input every file's token stream joins a single comparison
    stream. On `single_file` input the file is self-compared: only
    repeated code inside that file (two or more non-overlapping
    occurrences) can match, so a lone function with no internal
    repetition reports density 0.0 — a value is never fabricated
    for an Input with nothing to compare. `completeness` is `full`
    when every file tokenizes and `partial` (with a reason) when a
    file fails to tokenize — its lines and tokens are excluded,
    never assumed. A file that tokenizes but fails to `ast.parse`
    still joins the comparison (its duplication value is real);
    its occurrences carry no entity/kind attribution (those fields
    are null) and the file is listed in `unattributed_files`, so
    the UI can explain why instead of showing silent dashes.
    """

    MIN_TOKENS = 100
    MIN_LINES = 10

    def __init__(
            self,
            *,
            min_tokens: int = MIN_TOKENS,
            min_lines: int = MIN_LINES,
    ):
        self.min_tokens = min_tokens
        self.min_lines = min_lines

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> float | None:
        detail = self.calculate_detailed(
            python_files,
            scope,
        )

        return detail.get("density")

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:
        # Single-file inputs are analyzed too: the file is compared
        # against itself, so repeated code inside it is reported
        # (e.g. one function copied twice). Without internal
        # repetition the density is 0.0 with `completeness: full`.
        return self._analyze_project(
            python_files,
            scope,
        )

    # ---- Project analysis ----

    def _analyze_project(
            self,
            python_files: list[Path],
            scope: str | None,
    ) -> dict:
        stream = []
        successful_files = []
        failed_files = []
        unattributed_files = []
        indexes = {}

        for file_path in python_files:
            try:
                source_code = file_path.read_text(
                    encoding="utf-8"
                )
                tokens = self._tokenize_source(source_code)
            except (
                    tokenize.TokenError,
                    IndentationError,
                    SyntaxError,
            ) as exc:
                failed_files.append(
                    f"{file_path} ({exc})"
                )
                continue

            successful_files.append(file_path)

            tree = self._parse_source(source_code)

            if tree is None:
                unattributed_files.append(str(file_path))
            else:
                indexes[str(file_path)] = self._build_index(tree)

            stream.extend(
                {
                    "text": text,
                    "file": str(file_path),
                    "line": line,
                }
                for text, line in tokens
            )

        clones = self._find_clones(stream)

        blocks = []
        duplicated_lines = set()
        duplicated_token_indices = set()

        for group_index, clone in enumerate(clones):
            length = clone["length"]
            starts = clone["starts"]
            copies = len(starts)

            occurrences = []

            for ordinal, start in enumerate(
                    starts,
                    start=1,
            ):
                end = start + length - 1

                start_line = stream[start]["line"]
                end_line = self._block_end_line(
                    stream,
                    end,
                )

                file_name = stream[start]["file"]

                block = {
                    "file": file_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "group": group_index,
                    "copies": copies,
                    "ordinal": ordinal,
                }

                block.update(
                    self._region_attribution(
                        indexes.get(file_name),
                        start_line,
                        end_line,
                    )
                )

                occurrences.append(block)

                for line in range(start_line, end_line + 1):
                    duplicated_lines.add(
                        (file_name, line)
                    )

                duplicated_token_indices.update(
                    range(start, end + 1)
                )

            blocks.extend(occurrences)

        lines_of_code = self._lines_of_code(
            successful_files,
            scope,
        )

        density = (
            len(duplicated_lines) / lines_of_code * 100
            if lines_of_code > 0
            else 0.0
        )

        completeness = (
            "partial"
            if failed_files
            else "full"
        )

        detail = {
            "metric": "DUPLICATION",
            "scope": scope,
            "completeness": completeness,
            "lines_of_code": lines_of_code,
            "duplicated_lines": len(duplicated_lines),
            "duplicated_blocks": len(clones),
            "duplicated_tokens": len(
                duplicated_token_indices
            ),
            "density": density,
            "clones": clones,
            "blocks": blocks,
        }

        if failed_files:
            detail["reason"] = (
                "The following files could not be tokenized and "
                "were excluded from both the comparison and the "
                f"line count: {'; '.join(failed_files)}"
            )

        if unattributed_files:
            detail["unattributed_files"] = unattributed_files

        return detail

    # ---- Tokenizer / parser ----

    @staticmethod
    def _parse_source(source_code: str) -> ast.Module | None:
        """
        Best-effort AST parse for the entity/kind attribution of
        duplicated regions. A file that tokenizes but does not parse
        still participates in duplication detection — its blocks are
        simply reported without attribution (null fields).
        """
        try:
            return ast.parse(source_code)
        except (SyntaxError, ValueError):
            return None

    def _tokenize_source(
            self,
            source_code: str,
    ) -> list[tuple[str, int]]:
        tokens = []

        for token in tokenize.generate_tokens(
                io.StringIO(source_code).readline,
        ):
            if token.type in (
                    tokenize.COMMENT,
                    tokenize.NL,
                    tokenize.ENCODING,
                    tokenize.ENDMARKER,
            ):
                continue

            tokens.append(
                (
                    self._normalize_token(
                        token.type,
                        token.string,
                    ),
                    token.start[0],
                )
            )

        return tokens

    @staticmethod
    def _normalize_token(
            token_type: int,
            text: str,
    ) -> str:
        if token_type == tokenize.INDENT:
            return _INDENT_MARKER

        if token_type == tokenize.DEDENT:
            return _DEDENT_MARKER

        if token_type == tokenize.STRING:
            return _strip_string_prefix(text)

        return text

    # ---- Region attribution (AST explainability) ----

    def _build_index(self, tree: ast.Module) -> dict:
        """
        Per-file AST index used to attribute duplicated regions to
        named constructs: the node→parent map (a function defined
        directly in a class body is a method) plus every function/
        method/class node in the file.
        """
        parents = {}
        named = []

        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        for node in ast.walk(tree):
            if _is_named_construct(node):
                named.append(node)

        return {
            "root": tree,
            "parents": parents,
            "named": named,
        }

    @staticmethod
    def _entity_fields(
            node,
            parents: dict,
    ) -> tuple[str, str, str | None]:
        """
        The explainable-detail entity triple for a named construct:
        a function defined directly in a class body is a method (with
        its containing class); module-level and nested functions are
        plain functions; a class names itself.
        """
        if isinstance(node, ast.ClassDef):
            return (node.name, "class", None)

        if isinstance(parents.get(node), ast.ClassDef):
            return (node.name, "method", parents[node].name)

        return (node.name, "function", None)

    def _child_bodies(self, node) -> list[list[ast.stmt]]:
        """The statement bodies nested directly inside a node."""
        bodies = []

        if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            bodies.append(node.body)

        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            bodies.append(node.body)
            if node.orelse:
                bodies.append(node.orelse)

        elif isinstance(node, ast.If):
            bodies.append(node.body)
            if node.orelse:
                bodies.append(node.orelse)

        elif isinstance(node, ast.Try):
            bodies.append(node.body)
            bodies.extend(
                handler.body
                for handler in node.handlers
            )
            if node.orelse:
                bodies.append(node.orelse)
            if node.finalbody:
                bodies.append(node.finalbody)

        elif isinstance(node, (ast.With, ast.AsyncWith)):
            bodies.append(node.body)

        elif isinstance(node, ast.Match):
            bodies.extend(
                case.body
                for case in node.cases
            )

        return bodies

    def _collect_contained_statements(
            self,
            statements: list[ast.stmt],
            start_line: int,
            end_line: int,
            out: list[ast.stmt],
    ) -> None:
        """
        The statement nodes fully contained in the region [start_line,
        end_line], measured at the region's own nesting level (a
        contained compound is recorded and its nested statements are
        not descended into).
        """
        for stmt in statements:
            end = _node_end(stmt)

            if stmt.lineno >= start_line and end <= end_line:
                out.append(stmt)
                continue

            # The statement intersects the region without being fully
            # inside it — descend into its nested bodies so a
            # duplicated inner block is still attributed.
            if stmt.lineno <= end_line and end >= start_line:
                for body in self._child_bodies(stmt):
                    self._collect_contained_statements(
                        body,
                        start_line,
                        end_line,
                        out,
                    )

    def _region_attribution(
            self,
            index: dict | None,
            start_line: int,
            end_line: int,
    ) -> dict:
        """
        Entity + kind fields for one duplicated occurrence.

        `kind` describes the construct the region itself is:
          - "function"/"method"/"class" when the region is one whole
            named construct (its header lies inside the region);
          - the label of a single contained statement (a for/while
            loop, if/elif/else, try/except, with block, an
            assignment, …);
          - "statements" for a sequence of statements — including a
            whole duplicated file and a duplicated body whose
            headers differ (the two copies then keep their own
            enclosing entity names).

        `entity`/`entity_type`/`class_name` name the nearest
        containing function/method/class, or the module when the
        region sits at module level (entity None, entity_type
        "module"). All four fields are None only when the file did
        not parse. The physical `start_line`/`end_line` of the
        occurrence are always authoritative over these labels.
        """
        if index is None:
            return {
                "entity": None,
                "entity_type": None,
                "class_name": None,
                "kind": None,
            }

        contained = []
        self._collect_contained_statements(
            index["root"].body,
            start_line,
            end_line,
            contained,
        )

        if (
                len(contained) == 1
                and _is_named_construct(contained[0])
        ):
            entity, entity_type, class_name = self._entity_fields(
                contained[0],
                index["parents"],
            )

            return {
                "entity": entity,
                "entity_type": entity_type,
                "class_name": class_name,
                "kind": entity_type,
            }

        enclosing = [
            node
            for node in index["named"]
            if node.lineno <= start_line
            and _node_end(node) >= end_line
        ]

        if len(contained) == 1:
            kind = _construct_kind(contained[0])
        else:
            kind = "statements"

        if enclosing:
            innermost = max(
                enclosing,
                key=lambda node: node.lineno,
            )
            entity, entity_type, class_name = self._entity_fields(
                innermost,
                index["parents"],
            )
        else:
            entity, entity_type, class_name = (
                None,
                "module",
                None,
            )

        return {
            "entity": entity,
            "entity_type": entity_type,
            "class_name": class_name,
            "kind": kind,
        }

    # ---- Clone detection ----

    def _find_clones(
            self,
            stream: list[dict],
    ) -> list[dict]:
        """
        Find all maximal repeated token sequences of at least
        `min_tokens` tokens with at least two occurrences.
        """
        if len(stream) < 2 * self.min_tokens:
            return []

        texts = [
            item["text"]
            for item in stream
        ]

        hashes = self._window_hashes(
            texts,
            self.min_tokens,
        )

        groups = defaultdict(list)

        for index, hash_value in enumerate(hashes):
            groups[hash_value].append(index)

        clones = []
        seen = set()

        for starts in groups.values():
            if len(starts) < 2:
                continue

            starts = sorted(starts)

            starts = self._drop_overlapping_windows(
                stream,
                starts,
            )

            if len(starts) < 2:
                continue

            result = self._maximal_group(
                texts,
                stream,
                starts,
            )

            if result is None:
                continue

            starts, length = result

            key = (
                length,
                frozenset(starts),
            )

            if key in seen:
                continue

            seen.add(key)

            if not self._meets_line_minimum(
                    stream,
                    starts,
                    length,
            ):
                continue

            clones.append(
                {
                    "length": length,
                    "starts": starts,
                }
            )

        clones.sort(
            key=lambda clone: (
                -clone["length"],
                clone["starts"][0],
            )
        )

        return self._canonicalize_clones(
            clones,
            stream,
        )

    def _canonicalize_clones(
            self,
            clones: list[dict],
            stream: list[dict],
    ) -> list[dict]:
        """
        Drop redundant clone groups so `duplicated_blocks` counts the
        maximal repeated sequences, never their phase shifts or inner
        repetitions.

        A periodic file (e.g. twelve copies of one 72-line unit)
        produces, next to the real copy of the unit, dozens of
        *rotation* groups: equal-length windows that start inside one
        copy and run over the boundary into the next (lines 49–120,
        50–121, …). Every such occurrence is already covered by the
        occurrences of the copy itself, so the group adds no new
        duplicated content. Clone groups are processed longest-first
        (ties by earliest start); a group is kept only when at least
        one of its occurrences extends beyond the token intervals
        already covered by kept groups for that file. Coverage is per
        file, so two independently duplicated chunks in different
        regions (or files) are both kept.
        """
        kept = []
        covered_by_file = {}

        for clone in clones:
            length = clone["length"]
            spans_by_file = defaultdict(list)

            for start in clone["starts"]:
                file_name = stream[start]["file"]
                spans_by_file[file_name].append(
                    (start, start + length - 1)
                )

            if all(
                    self._spans_are_covered(
                        spans,
                        covered_by_file.get(file_name, []),
                    )
                    for file_name, spans in spans_by_file.items()
            ):
                continue

            kept.append(clone)

            for file_name, spans in spans_by_file.items():
                covered_by_file[file_name] = self._merge_spans(
                    covered_by_file.get(file_name, []),
                    spans,
                )

        return kept

    @staticmethod
    def _spans_are_covered(
            spans: list[tuple[int, int]],
            merged_intervals: list[tuple[int, int]],
    ) -> bool:
        """
        True when every [start, end] span lies fully inside one of
        the already-merged kept intervals of the same file.
        """
        if not merged_intervals:
            return False

        for start, end in spans:
            if not any(
                    low <= start and end <= high
                    for low, high in merged_intervals
            ):
                return False

        return True

    @staticmethod
    def _merge_spans(
            intervals: list[tuple[int, int]],
            extra: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Sorted, merged token intervals (adjacent spans merge)."""
        combined = sorted(intervals + extra)
        merged = []

        for start, end in combined:
            if (
                    merged
                    and start <= merged[-1][1] + 1
            ):
                merged[-1] = (
                    merged[-1][0],
                    max(merged[-1][1], end),
                )
            else:
                merged.append((start, end))

        return merged

    def _window_hashes(
            self,
            texts: list[str],
            window: int,
    ) -> list[int]:
        count = len(texts) - window + 1

        hashes = [0] * count

        rolling = 0

        for index in range(window):
            rolling = (
                rolling * _HASH_BASE
                + _token_hash(texts[index])
            ) % _HASH_MOD

        hashes[0] = rolling

        power = pow(_HASH_BASE, window, _HASH_MOD)

        for index in range(1, count):
            rolling = (
                rolling * _HASH_BASE
                - _token_hash(texts[index - 1]) * power
                + _token_hash(texts[index + window - 1])
            ) % _HASH_MOD

            hashes[index] = rolling

        return hashes

    def _drop_overlapping_windows(
            self,
            stream: list[dict],
            starts: list[int],
    ) -> list[int]:
        """
        Two windows of the same group must not overlap within the
        same file; overlapping windows represent the same repeated
        region, so the earliest one is kept.
        """
        kept = []
        last_end = {}

        for start in starts:
            file_name = stream[start]["file"]

            if start < last_end.get(file_name, 0):
                continue

            kept.append(start)
            last_end[file_name] = start + self.min_tokens

        return kept

    def _maximal_group(
            self,
            texts: list[str],
            stream: list[dict],
            starts: list[int],
    ) -> tuple[list[int], int] | None:
        """
        Verify the windows match (hash-collision guard) and expand
        them left and right to the maximal common repeat, keeping
        occurrences non-overlapping within the same file.
        """
        window = self.min_tokens
        total = len(texts)

        reference = texts[starts[0]:starts[0] + window]

        for start in starts[1:]:
            if texts[start:start + window] != reference:
                return None

        length = window

        # Right expansion.
        while True:
            next_indexes = [
                start + length
                for start in starts
            ]

            if any(
                    index >= total
                    for index in next_indexes
            ):
                break

            if self._would_overlap_right(
                    stream,
                    starts,
                    length,
            ):
                break

            token = texts[next_indexes[0]]

            if not all(
                    texts[index] == token
                    for index in next_indexes
            ):
                break

            length += 1

        # Left expansion.
        while True:
            previous_indexes = [
                start - 1
                for start in starts
            ]

            if any(
                    index < 0
                    for index in previous_indexes
            ):
                break

            if self._would_overlap_left(
                    stream,
                    starts,
                    length,
            ):
                break

            token = texts[previous_indexes[0]]

            if not all(
                    texts[index] == token
                    for index in previous_indexes
            ):
                break

            starts = previous_indexes
            length += 1

        return starts, length

    @staticmethod
    def _would_overlap_right(
            stream: list[dict],
            starts: list[int],
            length: int,
    ) -> bool:
        """
        An occurrence must not run into the next occurrence of the
        same group within the same file.
        """
        for index, start in enumerate(starts):
            file_name = stream[start]["file"]

            for other in starts[index + 1:]:
                if stream[other]["file"] != file_name:
                    continue

                return start + length >= other

        return False

    @staticmethod
    def _would_overlap_left(
            stream: list[dict],
            starts: list[int],
            length: int,
    ) -> bool:
        """
        An occurrence must not move back into the previous
        occurrence of the same group within the same file.
        """
        for index, start in enumerate(starts):
            if index == 0:
                continue

            file_name = stream[start]["file"]

            for other in starts[index - 1::-1]:
                if stream[other]["file"] != file_name:
                    continue

                return start - 1 < other + length

        return False

    @staticmethod
    def _block_end_line(
            stream: list[dict],
            end: int,
    ) -> int:
        """
        The physical line of the block's last content token. A
        trailing INDENT/DEDENT marker is zero-width and positioned
        on the line following the block's content, so it is stepped
        over when computing the block's line range.
        """
        while (
                end > 0
                and stream[end]["text"] in (
                    _INDENT_MARKER,
                    _DEDENT_MARKER,
                )
        ):
            end -= 1

        return stream[end]["line"]

    def _meets_line_minimum(
            self,
            stream: list[dict],
            starts: list[int],
            length: int,
    ) -> bool:
        """
        A clone group is kept only when every occurrence spans at
        least `min_lines` distinct physical lines.
        """
        for start in starts:
            start_line = stream[start]["line"]
            end_line = self._block_end_line(
                stream,
                start + length - 1,
            )

            if end_line - start_line + 1 < self.min_lines:
                return False

        return True

    # ---- Denominator (physical lines) ----

    def _lines_of_code(
            self,
            python_files: list[Path],
            scope: str | None,
    ) -> int:
        """
        The density denominator: the number of physical lines over
        the successfully tokenized files (radon `loc` — comments and
        blank lines included), matching the SonarQube formula
        `duplicated_lines_density = duplicated_lines / lines * 100`,
        whose `lines` is the physical-line measure. Using physical
        lines keeps the ratio inside [0, 100] even when a duplicated
        region covers comment/blank lines.
        """
        if not python_files:
            return 0

        detail = LOCEngine().calculate_detailed(
            python_files,
            scope,
        )

        return detail["totals"]["loc"]
