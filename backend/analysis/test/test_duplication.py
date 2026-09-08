import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from analysis.engines import ENGINE_REGISTRY, get_engine
from analysis.engines.duplication import DuplicationEngine
from analysis.models import MetricDefinition


# Fixture sources. Token counts below are the comparison-stream
# counts (comments, NL, blank lines, string prefixes excluded),
# verified against the standard-library tokenizer.
DUPLICATE_FN = (
    "def compute(x):\n"
    "    total = 0\n"
    "    total += x\n"
    "    total *= 2\n"
    "    return total\n"
)  # 24 tokens, lines 1-5, sloc 5

UNIQUE_FN = (
    "def unique():\n"
    "    return 99\n"
)  # 11 tokens, lines 1-2, sloc 2

ASSIGN3 = (
    "a = 1\n"
    "b = 2\n"
    "c = 3\n"
)  # 12 tokens, lines 1-3, sloc 3

ASSIGN2 = (
    "a = 1\n"
    "b = 2\n"
)  # 8 tokens, lines 1-2, sloc 2

ASSIGN2_PASS = (
    "a = 1\n"
    "b = 2\n"
    "pass\n"
)  # 10 tokens, lines 1-3, sloc 3


def analyze(
        sources: dict[str, str],
        *,
        scope: str = "project",
        **engine_kwargs,
) -> dict:
    """Run the engine over named sources in a temp directory."""
    engine = DuplicationEngine(**engine_kwargs)

    with tempfile.TemporaryDirectory() as temp_dir:
        paths = []

        for name, source in sources.items():
            path = Path(temp_dir) / name
            path.write_text(source, encoding="utf-8")
            paths.append(path)

        return engine.calculate_detailed(
            paths,
            scope=scope,
        )


class SingleFileInputTest(SimpleTestCase):
    """
    A single-file input is analyzed by comparing the file's own
    token stream against itself (ADR-0001): only repeated code
    inside that file can match, so nothing outside the input is
    ever assumed.
    """

    def test_single_file_without_internal_repetition_is_zero(self):
        detail = analyze(
            {"a.py": DUPLICATE_FN + UNIQUE_FN},
            scope="single_file",
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["scope"],
            "single_file",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertNotIn(
            "reason",
            detail,
        )

        self.assertEqual(
            detail["density"],
            0.0,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            0,
        )

        self.assertEqual(
            detail["lines_of_code"],
            7,
        )

    def test_single_file_detects_function_copied_twice(self):
        # The same function appears twice inside the one analyzed
        # file: both occurrences live in that file and both count.
        detail = analyze(
            {"a.py": DUPLICATE_FN + "\n" + DUPLICATE_FN},
            scope="single_file",
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            10,
        )

        self.assertEqual(
            detail["duplicated_tokens"],
            48,
        )

        self.assertEqual(
            detail["lines_of_code"],
            11,
        )

        # Physical-line denominator (SonarQube `lines`): the blank
        # separator line between the two copies is not duplicated but
        # is part of the denominator, so the density stays < 100.
        self.assertAlmostEqual(
            detail["density"],
            10 / 11 * 100,
        )

        self.assertEqual(
            len(detail["blocks"]),
            2,
        )

        for block in detail["blocks"]:
            self.assertTrue(
                block["file"].endswith("a.py"),
                block,
            )
            self.assertEqual(
                block["end_line"] - block["start_line"] + 1,
                5,
            )
            # The duplicated construct is the whole function
            # `compute`, repeated twice in the one file: both
            # occurrences share the clone group and carry the same
            # explainable entity/kind attribution.
            self.assertEqual(
                block["group"],
                0,
            )
            self.assertEqual(
                block["copies"],
                2,
            )
            self.assertEqual(
                block["entity"],
                "compute",
            )
            self.assertEqual(
                block["entity_type"],
                "function",
            )
            self.assertEqual(
                block["kind"],
                "function",
            )
            self.assertIsNone(
                block["class_name"],
            )

        self.assertEqual(
            {block["ordinal"] for block in detail["blocks"]},
            {1, 2},
        )

    def test_single_file_unparsable_reports_partial(self):
        detail = analyze(
            {"a.py": "def broken(:\n"},
            scope="single_file",
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["completeness"],
            "partial",
        )

        self.assertTrue(
            detail["reason"],
        )

        self.assertEqual(
            detail["density"],
            0.0,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

    def test_single_file_calculate_returns_density(self):
        engine = DuplicationEngine(
            min_tokens=10,
            min_lines=2,
        )

        with tempfile.NamedTemporaryFile(
                suffix=".py",
                delete=False,
                mode="w",
                encoding="utf-8",
        ) as temp_file:
            temp_file.write(
                DUPLICATE_FN + "\n" + DUPLICATE_FN
            )
            path = Path(temp_file.name)

        try:
            value = engine.calculate(
                [path],
                scope="single_file",
            )
        finally:
            path.unlink()

        self.assertAlmostEqual(
            value,
            10 / 11 * 100,
        )


class CrossFileDuplicationTest(SimpleTestCase):

    def test_exact_copy_across_files(self):
        detail = analyze(
            {
                "a.py": DUPLICATE_FN + UNIQUE_FN,
                "b.py": DUPLICATE_FN,
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            10,
        )

        self.assertEqual(
            detail["duplicated_tokens"],
            48,
        )

        self.assertEqual(
            detail["lines_of_code"],
            12,
        )

        self.assertAlmostEqual(
            detail["density"],
            10 / 12 * 100,
        )

        self.assertEqual(
            len(detail["blocks"]),
            2,
        )

        for block in detail["blocks"]:
            self.assertEqual(
                block["end_line"] - block["start_line"] + 1,
                5,
            )
            # The copied construct is the whole function `compute`
            # (one occurrence per file) — both rows carry the same
            # clone group, entity and kind.
            self.assertEqual(
                block["group"],
                0,
            )
            self.assertEqual(
                block["copies"],
                2,
            )
            self.assertEqual(
                block["entity"],
                "compute",
            )
            self.assertEqual(
                block["entity_type"],
                "function",
            )
            self.assertEqual(
                block["kind"],
                "function",
            )
            self.assertIsNone(
                block["class_name"],
            )

        self.assertEqual(
            {block["ordinal"] for block in detail["blocks"]},
            {1, 2},
        )

    def test_no_duplication(self):
        detail = analyze(
            {
                "a.py": DUPLICATE_FN,
                "b.py": UNIQUE_FN,
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            0,
        )

        self.assertEqual(
            detail["density"],
            0.0,
        )

    def test_entire_file_duplication_is_100_percent(self):
        detail = analyze(
            {
                "a.py": DUPLICATE_FN + UNIQUE_FN,
                "b.py": DUPLICATE_FN + UNIQUE_FN,
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            14,
        )

        self.assertAlmostEqual(
            detail["density"],
            100.0,
        )

    def test_formatting_differences_still_match(self):
        # Same tokens, different whitespace around operators.
        condensed = (
            "def compute(x):\n"
            "    total=0\n"
            "    total+=x\n"
            "    total*=2\n"
            "    return total\n"
        )

        detail = analyze(
            {
                "a.py": DUPLICATE_FN,
                "b.py": condensed,
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            10,
        )

        self.assertAlmostEqual(
            detail["density"],
            100.0,
        )

    def test_identifier_rename_is_not_detected(self):
        renamed = (
            "d = 1\n"
            "e = 2\n"
            "f = 3\n"
        )

        detail = analyze(
            {
                "a.py": ASSIGN3,
                "b.py": renamed,
            },
            min_tokens=10,
            min_lines=2,
        )

        # Type-1 semantics: renamed identifiers break the match.
        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            0,
        )


class ThresholdTest(SimpleTestCase):

    def test_block_below_token_minimum_never_counts(self):
        # 10-token block, minimum 11: below the minimum.
        detail = analyze(
            {
                "a.py": ASSIGN2_PASS,
                "b.py": ASSIGN2_PASS,
            },
            min_tokens=11,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["density"],
            0.0,
        )

    def test_block_at_token_minimum_counts(self):
        # 10-token block, minimum 10: at the minimum.
        detail = analyze(
            {
                "a.py": ASSIGN2_PASS,
                "b.py": ASSIGN2_PASS,
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            6,
        )

        self.assertAlmostEqual(
            detail["density"],
            100.0,
        )

    def test_block_below_line_minimum_never_counts(self):
        # 2-line block, minimum 3 lines: below the minimum.
        detail = analyze(
            {
                "a.py": ASSIGN2,
                "b.py": ASSIGN2,
            },
            min_tokens=8,
            min_lines=3,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["density"],
            0.0,
        )

    def test_block_at_line_minimum_counts(self):
        # 2-line block, minimum 2 lines: at the minimum.
        detail = analyze(
            {
                "a.py": ASSIGN2,
                "b.py": ASSIGN2,
            },
            min_tokens=8,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            4,
        )

        self.assertAlmostEqual(
            detail["density"],
            100.0,
        )

    def test_default_thresholds_require_100_tokens(self):
        # The 24-token block must NOT count with the default
        # minimum of 100 tokens.
        detail = analyze(
            {
                "a.py": DUPLICATE_FN,
                "b.py": DUPLICATE_FN,
            },
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["density"],
            0.0,
        )

    def test_default_thresholds_detect_large_clone(self):
        # A 30-line function = 123 tokens, 30 lines: above both
        # default minimums (100 tokens / 10 lines).
        big_function = (
            "def dup():\n"
            + "".join(
                f"    v{i} = 0\n"
                for i in range(28)
            )
            + "    return v0\n"
        )

        detail = analyze(
            {
                "a.py": big_function,
                "b.py": big_function,
            },
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            60,
        )

        self.assertEqual(
            detail["duplicated_tokens"],
            246,
        )

        self.assertEqual(
            detail["lines_of_code"],
            60,
        )

        self.assertAlmostEqual(
            detail["density"],
            100.0,
        )


class PartialCompletenessTest(SimpleTestCase):

    def test_unparsable_file_reports_partial(self):
        detail = analyze(
            {
                "a.py": ASSIGN3,
                "b.py": "def broken(:\n",
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["completeness"],
            "partial",
        )

        self.assertTrue(
            detail["reason"],
        )

        # Detection still runs on the parseable file alone.
        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        self.assertEqual(
            detail["lines_of_code"],
            3,
        )


class DuplicationEngineTest(SimpleTestCase):

    def test_calculate_returns_density(self):
        engine = DuplicationEngine(
            min_tokens=10,
            min_lines=2,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path_a = Path(temp_dir) / "a.py"
            path_b = Path(temp_dir) / "b.py"

            path_a.write_text(
                DUPLICATE_FN + UNIQUE_FN,
                encoding="utf-8",
            )
            path_b.write_text(
                DUPLICATE_FN,
                encoding="utf-8",
            )

            value = engine.calculate(
                [path_a, path_b],
                scope="project",
            )

        self.assertAlmostEqual(
            value,
            10 / 12 * 100,
        )

    def test_calculate_returns_zero_without_files(self):
        engine = DuplicationEngine()

        self.assertEqual(
            engine.calculate([]),
            0.0,
        )

    def test_engine_is_registered(self):
        self.assertIn(
            "DUPLICATION",
            ENGINE_REGISTRY,
        )

        engine = get_engine("DUPLICATION")

        self.assertIsInstance(
            engine,
            DuplicationEngine,
        )


class ExplainableBlockDetailTest(SimpleTestCase):
    """
    Every duplicated occurrence carries the explainable-detail fields
    so the UI can say *what* was repeated and *where*: `group`/
    `ordinal`/`copies` tie the copies of one clone group together,
    and `entity`/`entity_type`/`class_name`/`kind` name the
    duplicated construct and its containing function/class.
    """

    def test_renamed_function_copies_are_attributed_to_each_own_name(self):
        # Two functions share an identical signature and body but have
        # different names. The maximal repeat covers the whole def
        # (the token match bridges from the header's closing parens
        # through the body), so each occurrence is attributed to its
        # own function with kind "function" — the user sees "function
        # alpha is a copy of function beta" instead of anonymous lines.
        body = "".join(
            f"    v{i} = 0\n"
            for i in range(30)
        ) + "    return v0\n"

        detail = analyze(
            {
                "a.py": (
                    "def alpha():\n"
                    + body
                    + "\n"
                    "def beta():\n"
                    + body
                ),
            },
            scope="single_file",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            [block["entity"] for block in detail["blocks"]],
            ["alpha", "beta"],
        )

        for block in detail["blocks"]:
            self.assertEqual(
                block["entity_type"],
                "function",
            )
            self.assertEqual(
                block["kind"],
                "function",
            )
            self.assertIsNone(
                block["class_name"],
            )

    def test_duplicated_loop_inside_a_function_is_kind_for_loop(self):
        # The same for-loop is copied twice inside one function: each
        # occurrence is the whole loop (kind "for loop") living inside
        # `wrap`.
        loop = (
            "    for i in range(20):\n"
            + "".join(
                f"        v{i} = i + {i}\n"
                for i in range(26)
            )
        )

        detail = analyze(
            {
                "a.py": (
                    "def wrap():\n"
                    + loop
                    + "    marker = 1\n"
                    + loop
                ),
            },
            scope="single_file",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        for block in detail["blocks"]:
            self.assertEqual(
                block["entity"],
                "wrap",
            )
            self.assertEqual(
                block["entity_type"],
                "function",
            )
            self.assertEqual(
                block["kind"],
                "for loop",
            )
            self.assertIsNone(
                block["class_name"],
            )

    def test_duplicated_methods_within_a_class_carry_method_and_class(self):
        # The same method (signature + body, different name) is copied
        # twice inside one class: the whole def is the repeated
        # construct, each occurrence is a *method* and its class_name
        # is the owning class.
        method = (
            "    def handle(self, x):\n"
            "        total = 0\n"
            + "".join(
                f"        total += v{i}\n"
                for i in range(10)
            )
            + "        return total\n"
        )

        renamed = method.replace(
            "def handle(self, x):",
            "def helper(self, x):",
        )

        detail = analyze(
            {
                "a.py": (
                    "class Service:\n"
                    + method
                    + renamed
                ),
            },
            scope="single_file",
            min_tokens=20,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            [block["entity"] for block in detail["blocks"]],
            ["handle", "helper"],
        )

        for block in detail["blocks"]:
            self.assertEqual(
                block["entity_type"],
                "method",
            )
            self.assertEqual(
                block["kind"],
                "method",
            )
            self.assertEqual(
                block["class_name"],
                "Service",
            )

    def test_whole_class_copy_across_files_is_kind_class(self):
        detail = analyze(
            {
                "a.py": (
                    "class Service:\n"
                    "    def run(self):\n"
                    "        return 1\n"
                    "\n"
                    "    def stop(self):\n"
                    "        return 2\n"
                ),
                "b.py": (
                    "class Service:\n"
                    "    def run(self):\n"
                    "        return 1\n"
                    "\n"
                    "    def stop(self):\n"
                    "        return 2\n"
                ),
            },
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        for block in detail["blocks"]:
            self.assertEqual(
                block["entity"],
                "Service",
            )
            self.assertEqual(
                block["entity_type"],
                "class",
            )
            self.assertEqual(
                block["kind"],
                "class",
            )
            self.assertIsNone(
                block["class_name"],
            )

    def test_module_level_duplication_is_attributed_to_the_module(self):
        # A repeated block of top-level statements has no containing
        # function/class: the module is the entity and the construct
        # is a statement sequence.
        module_block = "".join(
            f"x{i} = {i}\n"
            for i in range(30)
        )

        detail = analyze(
            {
                "a.py": module_block + "\n" + module_block,
            },
            scope="single_file",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        for block in detail["blocks"]:
            self.assertIsNone(
                block["entity"],
            )
            self.assertEqual(
                block["entity_type"],
                "module",
            )
            self.assertEqual(
                block["kind"],
                "statements",
            )
            self.assertIsNone(
                block["class_name"],
            )


class CanonicalizationTest(SimpleTestCase):
    """
    `_canonicalize_clones` keeps only the maximal repeated sequences.
    A periodic file (one unit repeated many times) also matches in
    rotated windows that start inside a copy and cross the boundary
    into the next one — those groups add no new duplicated content
    and must not inflate `duplicated_blocks`.
    """

    def test_repeated_unit_is_reported_as_one_canonical_group(self):
        unit = (
            "def unit_0():\n"
            + "".join(
                f"    v{i} = {i}\n"
                for i in range(28)
            )
            + "    return v0\n"
        )

        # Six byte-identical copies inside one file (with blank
        # separators). The only real duplicated content is the unit
        # itself, copied six times.
        detail = analyze(
            {"a.py": "\n".join([unit] * 6)},
            scope="single_file",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        blocks = detail["blocks"]

        self.assertEqual(
            len(blocks),
            6,
        )

        self.assertEqual(
            {block["copies"] for block in blocks},
            {6},
        )

        self.assertEqual(
            {block["ordinal"] for block in blocks},
            set(range(1, 7)),
        )

        # One entity: the unit itself, in each of its copies.
        self.assertEqual(
            {block["entity"] for block in blocks},
            {"unit_0"},
        )

        self.assertEqual(
            {block["entity_type"] for block in blocks},
            {"function"},
        )

    def test_nested_inner_repeats_do_not_add_blocks(self):
        # Two identical inner segments inside each copy of a repeated
        # chunk: the inner repeats are already covered by the chunk's
        # own occurrences, so only the chunk is a duplicated block.
        inner = "".join(
            f"        w{i} = i\n"
            for i in range(28)
        )
        chunk = (
            "def chunk_0():\n"
            "    for i in range(3):\n"
            + inner
            + "    for i in range(3):\n"
            + inner
        )

        detail = analyze(
            {"a.py": "\n".join([chunk, chunk])},
            scope="single_file",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            len(detail["blocks"]),
            2,
        )

        self.assertEqual(
            {block["entity"] for block in detail["blocks"]},
            {"chunk_0"},
        )


class ParseFailureAttributionTest(SimpleTestCase):

    def test_parse_failing_file_is_listed_with_null_attribution(self):
        # Tokenizable but not parseable (missing body after `while`):
        # duplication itself is real and reported, the file is listed
        # in `unattributed_files`, and entity/kind stay null instead
        # of being guessed.
        broken = (
            "def broken(x):\n"
            "    while x\n"
            "    total = 1\n"
            "    return total\n"
        )

        detail = analyze(
            {"a.py": broken + "\n" + broken},
            scope="single_file",
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            len(detail["unattributed_files"]),
            1,
        )

        self.assertTrue(
            detail["unattributed_files"][0].endswith("a.py"),
        )

        for block in detail["blocks"]:
            self.assertIsNone(
                block["entity"],
            )
            self.assertIsNone(
                block["entity_type"],
            )
            self.assertIsNone(
                block["kind"],
            )


class DuplicationMetricSeedTest(TestCase):

    def test_duplication_definition_is_seeded(self):
        definition = MetricDefinition.objects.get(
            name="DUPLICATION",
        )

        self.assertEqual(
            definition.display_name,
            "Duplication",
        )

        self.assertEqual(
            definition.category,
            "Code Health",
        )

        self.assertFalse(
            definition.higher_is_better,
        )

        self.assertTrue(
            definition.supports_llm,
        )
