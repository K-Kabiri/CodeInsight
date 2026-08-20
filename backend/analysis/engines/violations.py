import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from .base import BaseMetricEngine


# Severity fallback used when a Ruff JSON record has no `severity`
# field: derive it from the rule code's category prefix.
_RUFF_SEVERITY_BY_PREFIX = {
    "E": "error",
    "F": "error",
    "W": "warning",
    "I": "info",
}


def _ruff_severity(rule_code: str) -> str:
    prefix = rule_code[0] if rule_code else ""
    return _RUFF_SEVERITY_BY_PREFIX.get(prefix, "warning")


def parse_ruff_output(output_text: str) -> list[dict]:
    """
    Convert `ruff check --output-format json` output into canonical
    violation records: {rule, severity, file, line, tool}.

    Each JSON item carries `code`, `filename`, `location.row`, and —
    since Ruff 0.16 — a native `severity` field; when the field is
    absent the severity is derived from the rule code's prefix
    (E/F -> error, W -> warning, I -> info, else warning).
    """
    data = json.loads(output_text)

    records = []

    for item in data:
        records.append(
            {
                "rule": item["code"],
                "severity": (
                    item.get("severity")
                    or _ruff_severity(item["code"])
                ),
                "file": item["filename"],
                "line": item["location"]["row"],
                "tool": "ruff",
            }
        )

    return records


def parse_bandit_output(output_text: str) -> list[dict]:
    """
    Convert `bandit -f json` output into canonical violation records:
    {rule, severity, file, line, tool}.

    Each result carries `test_id` (the B-code), `filename`,
    `line_number`, and `issue_severity` (HIGH/MEDIUM/LOW), normalized
    here to lowercase.
    """
    data = json.loads(output_text)

    records = []

    for item in data.get("results", []):
        records.append(
            {
                "rule": item["test_id"],
                "severity": item["issue_severity"].lower(),
                "file": item["filename"],
                "line": item["line_number"],
                "tool": "bandit",
            }
        )

    return records


def build_detail(
        scope: str | None,
        records: list[dict],
) -> dict:
    """
    Build the engine's detailed output from canonical records:
    total, per-rule, per-severity and per-file counts plus the
    records themselves. Applicable at any Scope, so completeness is
    always `full` (ADR-0001).
    """
    by_rule = Counter(
        record["rule"]
        for record in records
    )

    by_severity = Counter(
        record["severity"]
        for record in records
    )

    by_file = Counter(
        record["file"]
        for record in records
    )

    return {
        "metric": "VIOLATIONS",
        "scope": scope,
        "completeness": "full",
        "totals": {
            "violations": len(records),
            "files": len(by_file),
            "rules": len(by_rule),
        },
        "by_rule": dict(sorted(by_rule.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "by_file": dict(sorted(by_file.items())),
        "violations": records,
    }


class RuleViolationsEngine(BaseMetricEngine):
    """
    Rule Violations: lint and security findings over the analyzed
    Python files.

    A thin adapter runs Ruff (lint) and Bandit (security) in
    machine-readable mode and a parser converts their output into
    canonical violation records (rule, severity, file, line, tool).
    The scalar value is the total number of findings; the detailed
    output reports total, per-rule, per-severity and per-file counts.

    Rule set (documented, per the Code Health spec): Ruff runs its
    own default selection under `--isolated` (no configuration files
    from the analyzed project are honored) — as of Ruff 0.16 the
    zero-config default is 413 rules across the E/F/I/UP/B/S families
    (see the Ruff 0.16.0 release notes). Bandit runs its default
    security checks.

    Scope/completeness (ADR-0001): applicable at any Scope, so the
    detail always carries `completeness: full` for every analyzed
    file. Ruff and Bandit are in-process pip dependencies (ADR-0002);
    unit tests never execute them — the parser is the tested surface,
    exercised against hand-written output fixtures.
    """

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> int:
        detail = self.calculate_detailed(
            python_files,
            scope,
        )

        return detail["totals"]["violations"]

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:
        if not python_files:
            return build_detail(scope, [])

        ruff_output = _run_ruff(python_files)
        bandit_output = _run_bandit(python_files)

        records = []
        records.extend(parse_ruff_output(ruff_output))
        records.extend(parse_bandit_output(bandit_output))

        return build_detail(scope, records)


def _run_ruff(python_files: list[Path]) -> str:
    return _run_tool(
        command=[
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--output-format",
            "json",
            *[str(file_path) for file_path in python_files],
        ],
        tool_name="Ruff",
    )


def _run_bandit(python_files: list[Path]) -> str:
    return _run_tool(
        command=[
            sys.executable,
            "-m",
            "bandit",
            "-q",
            "-f",
            "json",
            *[str(file_path) for file_path in python_files],
        ],
        tool_name="Bandit",
    )


def _run_tool(
        command: list[str],
        tool_name: str,
) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"{tool_name} is not installed — add it to the runtime "
            "requirements."
        ) from exc

    # Both tools exit 1 when findings exist; stdout still carries the
    # machine-readable output. Any other exit code is a tool failure.
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"{tool_name} failed (exit {completed.returncode}): "
            f"{completed.stderr.strip()}"
        )

    return completed.stdout
