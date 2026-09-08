import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from analysis.engines import ENGINE_REGISTRY, get_engine
from analysis.engines.violations import (
    RuleViolationsEngine,
    _validate_tool_run,
    add_snippets,
    build_detail,
    parse_bandit_output,
    parse_ruff_output,
)
from analysis.models import MetricDefinition


# Hand-written fixtures modeled on the real machine-readable output
# of ruff 0.16.3 (`--output-format json`) and bandit 1.9.4 (`-f json`),
# with stable file names. Tests never execute the tools (ADR-0002).
RUFF_FIXTURE = """[
  {
    "cell": null,
    "code": "F401",
    "end_location": {"column": 10, "row": 1},
    "filename": "main.py",
    "fix": null,
    "location": {"column": 8, "row": 1},
    "message": "`os` imported but unused",
    "name": "unused-import",
    "noqa_row": 1,
    "severity": "error",
    "url": "https://docs.astral.sh/ruff/rules/unused-import"
  },
  {
    "cell": null,
    "code": "E722",
    "end_location": {"column": 11, "row": 11},
    "filename": "utils.py",
    "fix": null,
    "location": {"column": 5, "row": 11},
    "message": "Do not use bare `except`",
    "name": "bare-except",
    "noqa_row": 11,
    "severity": "error",
    "url": "https://docs.astral.sh/ruff/rules/bare-except"
  },
  {
    "cell": null,
    "code": "W291",
    "end_location": {"column": 5, "row": 3},
    "filename": "utils.py",
    "fix": null,
    "location": {"column": 1, "row": 3},
    "message": "Trailing whitespace",
    "name": "trailing-whitespace",
    "noqa_row": 3,
    "url": "https://docs.astral.sh/ruff/rules/trailing-whitespace"
  }
]
"""

BANDIT_FIXTURE = """{
  "errors": [],
  "generated_at": "2026-01-01T00:00:00Z",
  "metrics": {
    "_totals": {
      "CONFIDENCE.HIGH": 1,
      "CONFIDENCE.LOW": 0,
      "CONFIDENCE.MEDIUM": 0,
      "CONFIDENCE.UNDEFINED": 0,
      "SEVERITY.HIGH": 0,
      "SEVERITY.LOW": 1,
      "SEVERITY.MEDIUM": 0,
      "SEVERITY.UNDEFINED": 0,
      "loc": 9,
      "nosec": 0,
      "skipped_tests": 0
    }
  },
  "results": [
    {
      "code": "11     except:\\n12         pass\\n",
      "col_offset": 4,
      "end_col_offset": 12,
      "filename": "utils.py",
      "issue_confidence": "HIGH",
      "issue_cwe": {
        "id": 703,
        "link": "https://cwe.mitre.org/data/definitions/703.html"
      },
      "issue_severity": "LOW",
      "issue_text": "Try, Except, Pass detected.",
      "line_number": 11,
      "line_range": [11, 12],
      "more_info": "https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html",
      "test_id": "B110",
      "test_name": "try_except_pass"
    }
  ]
}
"""


class RuffOutputParserTest(SimpleTestCase):

    def test_parses_violation_records(self):
        records = parse_ruff_output(RUFF_FIXTURE)

        self.assertEqual(
            records,
            [
                {
                    "rule": "F401",
                    "severity": "error",
                    "file": "main.py",
                    "line": 1,
                    "column": 8,
                    "tool_message": "`os` imported but unused",
                    "snippet": None,
                    "tool": "ruff",
                },
                {
                    "rule": "E722",
                    "severity": "error",
                    "file": "utils.py",
                    "line": 11,
                    "column": 5,
                    "tool_message": "Do not use bare `except`",
                    "snippet": None,
                    "tool": "ruff",
                },
                {
                    "rule": "W291",
                    "severity": "warning",
                    "file": "utils.py",
                    "line": 3,
                    "column": 1,
                    "tool_message": "Trailing whitespace",
                    "snippet": None,
                    "tool": "ruff",
                },
            ],
        )

    def test_severity_is_derived_when_field_is_missing(self):
        # The W291 record above has no `severity` field: it must be
        # derived from the rule prefix (W -> warning).
        records = parse_ruff_output(RUFF_FIXTURE)

        by_rule = {
            record["rule"]: record["severity"]
            for record in records
        }

        self.assertEqual(
            by_rule["W291"],
            "warning",
        )


class BanditOutputParserTest(SimpleTestCase):

    def test_parses_violation_records(self):
        records = parse_bandit_output(BANDIT_FIXTURE)

        self.assertEqual(
            records,
            [
                {
                    "rule": "B110",
                    "severity": "low",
                    "file": "utils.py",
                    "line": 11,
                    "column": 4,
                    "tool_message": "Try, Except, Pass detected.",
                    "snippet": (
                        "11     except:\n"
                        "12         pass\n"
                    ),
                    "tool": "bandit",
                },
            ],
        )

    def test_empty_results_produce_no_records(self):
        records = parse_bandit_output('{"errors": [], "results": []}')

        self.assertEqual(
            records,
            [],
        )


class AddSnippetsTest(SimpleTestCase):

    def _write_source(self, source: str) -> Path:
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".py",
            delete=False,
            mode="w",
            encoding="utf-8",
        )
        temp_file.write(source)
        temp_file.close()
        return Path(temp_file.name)

    def test_fills_ruff_snippet_from_source_file(self):
        path = self._write_source(
            "import os\n"
            "x = 1\n"
        )

        try:
            records = add_snippets(
                [
                    {
                        "rule": "F401",
                        "severity": "error",
                        "file": str(path),
                        "line": 1,
                        "column": 8,
                        "tool_message": "`os` imported but unused",
                        "snippet": None,
                        "tool": "ruff",
                    },
                ]
            )
        finally:
            path.unlink()

        self.assertEqual(
            records[0]["snippet"],
            "import os",
        )

    def test_keeps_bandit_snippet(self):
        # Bandit's own `code` snippet is never overwritten.
        records = add_snippets(
            [
                {
                    "rule": "B110",
                    "severity": "low",
                    "file": "utils.py",
                    "line": 11,
                    "column": 4,
                    "tool_message": "Try, Except, Pass detected.",
                    "snippet": "except:\n    pass\n",
                    "tool": "bandit",
                },
            ]
        )

        self.assertEqual(
            records[0]["snippet"],
            "except:\n    pass\n",
        )

    def test_missing_file_keeps_snippet_none(self):
        records = add_snippets(
            [
                {
                    "rule": "F401",
                    "severity": "error",
                    "file": "does-not-exist.py",
                    "line": 1,
                    "column": 8,
                    "tool_message": "message",
                    "snippet": None,
                    "tool": "ruff",
                },
            ]
        )

        self.assertIsNone(
            records[0]["snippet"],
        )


class ViolationAggregationTest(SimpleTestCase):

    def _combined_records(self):
        records = []
        records.extend(parse_ruff_output(RUFF_FIXTURE))
        records.extend(parse_bandit_output(BANDIT_FIXTURE))
        return records

    def test_detail_reports_hand_computed_counts(self):
        detail = build_detail(
            "project",
            self._combined_records(),
        )

        self.assertEqual(
            detail["metric"],
            "VIOLATIONS",
        )

        self.assertEqual(
            detail["scope"],
            "project",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["totals"],
            {
                "violations": 4,
                "files": 2,
                "rules": 4,
            },
        )

        self.assertEqual(
            detail["by_rule"],
            {
                "B110": 1,
                "E722": 1,
                "F401": 1,
                "W291": 1,
            },
        )

        self.assertEqual(
            detail["by_severity"],
            {
                "error": 2,
                "low": 1,
                "warning": 1,
            },
        )

        self.assertEqual(
            detail["by_file"],
            {
                "main.py": 1,
                "utils.py": 3,
            },
        )

        self.assertEqual(
            len(detail["violations"]),
            4,
        )

    def test_empty_records_report_zero(self):
        detail = build_detail(
            "single_file",
            [],
        )

        self.assertEqual(
            detail["totals"]["violations"],
            0,
        )

        self.assertEqual(
            detail["by_rule"],
            {},
        )

        self.assertEqual(
            detail["by_severity"],
            {},
        )

        self.assertEqual(
            detail["by_file"],
            {},
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )


class RuleViolationsEngineTest(SimpleTestCase):

    def test_calculate_returns_zero_without_files(self):
        # No files means no tool invocation: the engine must return
        # a clean zero without executing Ruff or Bandit.
        engine = RuleViolationsEngine()

        self.assertEqual(
            engine.calculate([]),
            0,
        )

    def test_calculate_detailed_without_files_keeps_scope(self):
        engine = RuleViolationsEngine()

        detail = engine.calculate_detailed(
            [],
            scope="single_file",
        )

        self.assertEqual(
            detail["scope"],
            "single_file",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["totals"]["violations"],
            0,
        )

    def test_engine_is_registered(self):
        self.assertIn(
            "VIOLATIONS",
            ENGINE_REGISTRY,
        )

        engine = get_engine("VIOLATIONS")

        self.assertIsInstance(
            engine,
            RuleViolationsEngine,
        )


class ToolRunValidationTest(SimpleTestCase):
    """
    Exit-code handling of a finished tool invocation, tested with
    synthetic returncode/stdout/stderr triples — no tool is ever
    executed (ADR-0002).

    The behavior that pinned this test: when a tool is missing,
    `python -m <tool>` exits 1 (the same code as a findings run)
    with an empty stdout, and the engine used to hand that empty
    string to the JSON parsers, failing the metric with an opaque
    `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
    on every analysis.
    """

    def test_findings_run_exit_1_passes_stdout_through(self):
        stdout = _validate_tool_run(
            1,
            '["F401 finding"]',
            "",
            "Ruff",
        )

        self.assertEqual(
            stdout,
            '["F401 finding"]',
        )

    def test_clean_run_exit_0_passes_stdout_through(self):
        stdout = _validate_tool_run(
            0,
            "[]",
            "",
            "Ruff",
        )

        self.assertEqual(
            stdout,
            "[]",
        )

    def test_missing_module_raises_install_error(self):
        # `python -m ruff` with ruff not installed: exit 1, empty
        # stdout, "No module named ruff" on stderr. Must raise the
        # same clear message as the FileNotFoundError branch, never
        # return the empty stdout to the parser.
        with self.assertRaisesRegex(
            RuntimeError,
            "Ruff is not installed",
        ):
            _validate_tool_run(
                1,
                "",
                "No module named ruff",
                "Ruff",
            )

    def test_empty_stdout_with_other_stderr_raises(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "no output.*boom",
        ):
            _validate_tool_run(
                0,
                "",
                "boom",
                "Bandit",
            )

    def test_failure_exit_code_raises(self):
        with self.assertRaisesRegex(
            RuntimeError,
            r"failed \(exit 2\)",
        ):
            _validate_tool_run(
                2,
                "",
                "internal error",
                "Bandit",
            )


class ViolationsMetricSeedTest(TestCase):

    def test_violations_definition_is_seeded(self):
        definition = MetricDefinition.objects.get(
            name="VIOLATIONS",
        )

        self.assertEqual(
            definition.display_name,
            "Rule Violations",
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
