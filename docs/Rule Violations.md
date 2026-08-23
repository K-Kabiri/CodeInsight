# Rule Violations

## 1. Overview

**Rule Violations** is a code-health metric that counts lint and security findings produced by **external tools** — **Ruff** for linting and **Bandit** for security — executed against the analyzed Python files. The engine is a **thin adapter**: it runs the two tools in-process (as pip dependencies), parses their machine-readable JSON output into canonical violation records, and aggregates counts.

This metric is deliberately distinct from **Code Smells** (see [Code Smells.md](Code%20Smells.md)): a Rule Violation is an *objective* finding relative to a tool's rule set (Ruff's E722 either fires or it does not), while a Code Smell is a *curated heuristic* from CodeInsight's own AST engine.

## 2. Purpose

Rule Violations surfaces objective, tool-enforced problems — unused imports, undefined names, bare excepts, security issues like `try/except/pass` or hardcoded passwords — so the report distinguishes "the tools found these" from "our heuristics flagged these". Each record carries the rule code, severity, file, line, column, tool message and source snippet, making findings actionable rather than a bare count.

## 3. Reference Definition

There is no single academic "rule" for this metric — the definition is **the union of Ruff's and Bandit's rule sets**, as configured by the tools' defaults. What CodeInsight pins is the *contract*: a violation is a record with `rule, severity, file, line, column, tool_message, snippet, tool` (pinned by the cross-engine detail contract, `test_detail_contract.py:124-141`, with `column`/`snippet` nullable).

Per [CONTEXT.md](../CONTEXT.md): *"Rule Violation — A finding from a lint or security tool (Ruff, Bandit). Distinct from a Code Smell."* The engine's docstring documents the rule coverage: "413 rules across the E/F/I/UP/B/S families (as of Ruff 0.16)" (`violations.py:196-201`), i.e. Ruff's **zero-config default selection** plus Bandit's **default security checks**.

## 4. Implementation Basis: Library (Ruff + Bandit, executed and parsed)

The metric is **library-based in execution** and **hand-written in parsing/aggregation**:

- **Execution:** both tools run as subprocesses of the in-process pip dependency via `sys.executable -m` (never a bare executable name), so the pinned versions are used:
  - Ruff — `_run_ruff`, `violations.py:241-254`: `subprocess.run([sys.executable, "-m", "ruff", "check", "--isolated", "--output-format", "json", *files])`. `--isolated` guarantees the analyzed project's own config files cannot alter the rule set (`violations.py:196-201, 247-248`); there is **no explicit rule-selection flag** — Ruff's zero-config defaults are used.
  - Bandit — `_run_bandit`, `violations.py:257-269`: `subprocess.run([sys.executable, "-m", "bandit", "-q", "-f", "json", *files])` — quiet mode, JSON output, default checks.
  - Runner — `_run_tool`, `violations.py:272-296`: `capture_output=True, text=True`; `FileNotFoundError` → `RuntimeError("… is not installed — add it to the runtime requirements")` (`violations.py:282-286`); exit codes **0 or 1** accepted (both tools exit 1 when findings exist, stdout still carries the JSON; `violations.py:288-294`), anything else → `RuntimeError` with stderr.
- **Parsing:** hand-written — `parse_ruff_output` (`violations.py:25-64`) and `parse_bandit_output` (`violations.py:67-97`), see Section 5.
- Runtime dependencies: `ruff==0.16.3`, `bandit==1.9.4` (`backend/requirements.txt`). No ruff/bandit config files exist anywhere in the repo.

## 5. Calculation Steps in CodeInsight

1. **Run** Ruff and Bandit against the file list (`violations.py:241-269`); an **empty file list short-circuits with a clean zero** without invoking any tool (`violations.py:227-228`, pinned by `test_violations.py:383-391`).
2. **Parse Ruff JSON** (`violations.py:25-64`): per item — `rule=item["code"]`, `file=item["filename"]`, `line`/`column` from the location, `tool_message=item.get("message")`, `snippet=None`, `tool="ruff"`. Severity: native `item.get("severity")` when present, else derived from the rule-code prefix by `_ruff_severity` (`violations.py:20-22`; prefix map `violations.py:12-17`: E/F → error, W → warning, I → info, else warning).
3. **Parse Bandit JSON** (`violations.py:67-97`): iterate `data["results"]` — `rule=item["test_id"]`, `severity=item["issue_severity"].lower()`, `file`, `line=item["line_number"]`, `column=item.get("col_offset")`, `tool_message=item.get("issue_text")`, `snippet=item.get("code")` (Bandit's own snippet kept as-is), `tool="bandit"`; missing fields default to `None`.
4. **Fill snippets for Ruff records** (`add_snippets`, `violations.py:100-140`): the offending line is read from the file on disk (`Path.read_text` → `splitlines()` → index `lineno-1`, guarded `1 <= lineno <= len`, `violations.py:116-138`); unreadable file or out-of-range line keeps `None`. Bandit snippets are never overwritten.
5. **Aggregate** (`build_detail`, `violations.py:143-181`): `totals` (violations/files/rules), `by_rule`, `by_severity`, `by_file`, and the flat `violations` records; `metric="VIOLATIONS"`, `completeness: "full"` at any scope.

## 6. Scope and Completeness (ADR-0001)

Rule Violations is applicable at **any scope** (`single_file` or `project`) and reports `completeness: "full"`: the tools run on exactly the analyzed files, and findings are objective — there is no unobservable dependency to under-report (per the Code Health spec, Rule Violations and Code Smells "are applicable at any Scope (full)").

## 7. Limitations

- **Tool defaults are the rule set.** The engine deliberately uses each tool's zero-config defaults under `--isolated` — the analyzed project's ruff/bandit configuration is *never* honored. Tuning the rule set means changing the engine, not adding a config file.
- **Dynamic findings can vary.** Both tools analyze source text statically; findings are stable for the same tool version but change across tool upgrades (versions are pinned in `requirements.txt`).
- **Subprocess execution.** The engine shells out to the in-process interpreter (`sys.executable -m`); if a tool is missing from the environment, the engine raises instead of fabricating results.
- **Ruff snippets are single lines.** Ruff records get the one offending line as snippet (Bandit's multi-line snippets are kept as Bandit produced them).

## 8. Unit Tests

`backend/analysis/test/test_violations.py` — the parser is tested against **hand-written output fixtures, never by executing the tools** (ADR-0002; stated explicitly at `test_violations.py:17-19`):

- `RUFF_FIXTURE` (`test_violations.py:20-60`) — a hand-written array of 3 records modeled on real `ruff 0.16.3 --output-format json`: `F401` unused import (row 1, col 8, severity `error`), `E722` bare except (row 11, col 5, `error`), `W291` trailing whitespace (**no** `severity` field — exercises the prefix-fallback W → warning, `test_violations.py:145-158`).
- `BANDIT_FIXTURE` (`test_violations.py:62-101`) — a hand-written `bandit 1.9.4 -f json` object with one result `B110 try_except_pass` (line 11, `col_offset` 4, `issue_severity LOW`, issue text, code snippet, CWE 703).
- Tests cover: parser record shapes (`test_violations.py:104-191`), snippet filling against a temp file on disk (`:194-276`), hand-computed aggregation counts (4 violations / 2 files / 4 rules, `:279-378`), empty-input short-circuit (`:383-391`), registry and `MetricDefinition` seed (`:381-453`).
- Issue 04 (`.scratch/code-health/issues/04-rule-violations-engine.md:17`) records a one-time dev smoke test against the real tools (6 findings) — not part of the suite.

## 9. References

- Ruff rule index (E/F/I/UP/B/S families): [docs.astral.sh/ruff/rules](https://docs.astral.sh/ruff/rules/)
- Bandit (Python security linter): [bandit.readthedocs.io](https://bandit.readthedocs.io/)
- CodeInsight ADR-0002, standalone analyzer (tests never execute the tools): [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight glossary (Rule Violation vs Code Smell): [CONTEXT.md](../CONTEXT.md)
- Engine: `backend/analysis/engines/violations.py` · Tests: `backend/analysis/test/test_violations.py`
- Registration: `MetricDefinition` key `VIOLATIONS`, display name "Rule Violations", category "Code Health" (`backend/analysis/migrations/0006_seed_violations.py:11-24`)
