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
    Duplication (SonarQube semantics, per `docs/duplication.md`).

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
    `MIN_LINES` (default 10) distinct physical lines. Measures:

      duplicated_blocks = number of clone groups
      duplicated_lines  = union of physical lines in duplicated
                          blocks (each line counted once per file)
      duplicated_tokens = tokens lying inside duplicated blocks
      Duplication     = duplicated_lines / lines_of_code * 100,
                          where lines_of_code is the source-lines
                          count from the existing LOC engine (Radon
                          sloc) over the successfully tokenized files

    Scope/completeness (ADR-0001): on `single_file` Input the metric
    is `not_applicable` with a human-readable reason — a value is
    never fabricated for an Input with nothing to compare. On
    `project` Input the measure is computed with `completeness: full`
    when every file tokenizes, `partial` (with a reason) when a file
    fails to tokenize — its lines and tokens are excluded, never
    assumed.
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
        if scope == "single_file":
            return {
                "metric": "DUPLICATION",
                "scope": "single_file",
                "completeness": "not_applicable",
                "reason": (
                    "Duplication compares token streams across the "
                    "analyzed files — not applicable to a "
                    "single-file input."
                ),
                "lines_of_code": 0,
                "duplicated_lines": 0,
                "duplicated_blocks": 0,
                "duplicated_tokens": 0,
                "density": None,
                "clones": [],
                "blocks": [],
            }

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

        for file_path in python_files:
            try:
                tokens = self._tokenize_file(file_path)
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

        for clone in clones:
            length = clone["length"]

            occurrences = []

            for start in clone["starts"]:
                end = start + length - 1

                start_line = stream[start]["line"]
                end_line = self._block_end_line(
                    stream,
                    end,
                )

                file_name = stream[start]["file"]

                occurrences.append(
                    {
                        "file": file_name,
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )

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

        return detail

    # ---- Tokenizer ----

    def _tokenize_file(
            self,
            file_path: Path,
    ) -> list[tuple[str, int]]:
        source_code = file_path.read_text(encoding="utf-8")

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

        return clones

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

    # ---- Lines of code ----

    def _lines_of_code(
            self,
            python_files: list[Path],
            scope: str | None,
    ) -> int:
        if not python_files:
            return 0

        detail = LOCEngine().calculate_detailed(
            python_files,
            scope,
        )

        return detail["totals"]["sloc"]
