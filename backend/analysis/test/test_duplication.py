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

    def test_single_file_is_not_applicable(self):
        detail = analyze(
            {"a.py": DUPLICATE_FN},
            scope="single_file",
            min_tokens=10,
            min_lines=2,
        )

        self.assertEqual(
            detail["completeness"],
            "not_applicable",
        )

        self.assertTrue(
            detail["reason"],
        )

        self.assertIsNone(
            detail["density"],
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            0,
        )

        engine = DuplicationEngine()

        with tempfile.NamedTemporaryFile(
                suffix=".py",
                delete=False,
                mode="w",
                encoding="utf-8",
        ) as temp_file:
            temp_file.write(DUPLICATE_FN)
            path = Path(temp_file.name)

        try:
            value = engine.calculate(
                [path],
                scope="single_file",
            )
        finally:
            path.unlink()

        self.assertIsNone(
            value,
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


class DuplicationMetricSeedTest(TestCase):

    def test_duplication_definition_is_seeded(self):
        definition = MetricDefinition.objects.get(
            name="DUPLICATION",
        )

        self.assertEqual(
            definition.display_name,
            "Duplication %",
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
