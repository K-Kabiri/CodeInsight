# Duplication %

## 1. Overview

**Duplication %** is a code-health metric that measures how much of the analyzed codebase is repeated — the classic copy-paste ("clone") signal. CodeInsight follows the **SonarQube semantics** for this metric family: detection is **token-based** (source is tokenized, repeated token sequences are located, and the lines covered by those sequences are counted), and the headline value is a **lines-based ratio**: duplicated lines divided by lines of code.

In CodeInsight the metric is **fully hand-implemented**: a custom tokenizer on the standard `tokenize` module plus a hand-rolled **Rabin–Karp rolling-hash** matcher. There is no duplication library — `radon` is used only indirectly, for the source-lines denominator via the existing LOC engine.

## 2. Purpose

Duplicated code is a maintenance risk: a bug in a duplicated block must be fixed in every copy, and refactoring one copy without the others silently diverges behavior. The metric is interpreted together with the other maintainability metrics (LOC, complexity, coupling/cohesion) as a signal of copy-paste behavior, not as a standalone verdict.

## 3. Reference Definition (SonarQube)

SonarQube defines five duplication measures on its "Metric definitions" page ([docs.sonarsource.com — Metric definitions](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition)):

- `duplicated_blocks` — number of duplicated blocks of lines.
- `duplicated_files` — number of files involved in duplications.
- `duplicated_lines` — number of lines involved in duplications.
- `duplicated_lines_density` — **Duplicated lines (%)** — number of lines involved in duplications divided by the number of lines of code (LOC).
- `duplicated_tokens` — number of tokens involved in duplications.

The percentage is a **lines-based ratio, not a token-based ratio**:

```text
Duplicated lines (%) = duplicated_lines / lines_of_code * 100
```

The denominator is SonarQube's "Lines of code" measure (non-comment, non-blank lines, the `ncloc` measure) — in CodeInsight terms this maps to Radon's `sloc` produced by the existing LOC engine (`radon.raw.analyze`).

SonarQube's detection is token-based, computed by the platform core module `org.sonar.duplications` (tokenization in `org.sonar.duplications.token`, clone detection via a suffix-tree detector in `org.sonar.duplications.detector.suffixtree`); language plugins only supply the token stream. Default thresholds: a duplicated block needs at least **100 successive duplicated tokens** and must span a minimum of **10 lines** (both configurable).

Clone taxonomy (Bellon et al. 2007; Roy & Cordy 2007): **Type-1** = identical except whitespace/layout/comments; **Type-2** = additionally renamed identifiers/changed literals; **Type-3** = gapped modifications; **Type-4** = semantic clones. SonarQube and PMD CPD detect Type-1 (and near-exact) clones by default; CodeInsight does the same.

## 4. Implementation Basis: Manual (no library)

The duplication engine is **100% hand-implemented** — there is no maintained Python library that implements SonarQube-style token-based duplication with a "Duplication %" output (pydedupe is unrelated record-linkage software; pylint's R0801 is a line-similarity checker with no percentage/token counts; ruff has no clone rule; radon has no duplication detection; flay is AST-based, unmaintained and not SonarQube-compatible; jscpd is a Node.js CLI with jscpd's own semantics).

- Engine file: `backend/analysis/engines/duplication.py`
- **Tokenization:** the Python standard-library `tokenize` module (`duplication.py:3, 248-277`) — not a grammar tokenizer.
- **Matching:** a hand-rolled **Rabin–Karp rolling hash** (`duplication.py:20-21, 384-414`) with per-token `zlib.crc32` hashes (`duplication.py:26-27`), plus direct comparison to verify hash collisions.
- **Denominator:** Radon's `sloc` via the existing LOC engine — `from radon.raw import analyze` (`loc.py:4`), `result.sloc` (`loc.py:131`), delegated at `duplication.py:616-629`.
- Runtime dependencies: `radon==6.0.1` is the only analysis dep; no tokenizer/duplication library (`backend/requirements.txt`).

## 5. Calculation Steps in CodeInsight

**Tokenization** (`duplication.py:248-277`): each file is tokenized with `tokenize`; the comparison stream **drops** `COMMENT`, `NL`, `ENCODING`, `ENDMARKER` (comments and blank lines are invisible to matching, `duplication.py:259-265`) and **keeps** `NAME`, `OP`, `NUMBER`, `STRING`, keywords, `NEWLINE`, `INDENT`, `DEDENT` so statement structure is preserved. `INDENT`/`DEDENT` are normalized to the markers `"<INDENT>"`/`"<DEDENT>"`; string prefixes are stripped; all other token texts are kept as-is. This yields **Type-1 (exact) clone detection by default** — identifier renames break a match, exactly like SonarQube/CPD defaults. The streams of all files are concatenated into one stream of `{text, file, line}` triples.

**Detection** (`duplication.py:384-414`): rolling-hash buckets of `min_tokens`-sized windows (default 100) are built; overlapping same-file windows are dropped; hash collisions are verified by direct token comparison; matches are then expanded left/right to **maximal repeated sequences**. A clone group is kept only if **every occurrence spans at least `min_lines` (default 10) distinct physical lines** (`_meets_line_minimum`, `duplication.py:592-612`; `_block_end_line` `:570-590` steps over trailing INDENT/DEDENT).

**Measures** (`duplication.py:210-214`):

```text
duplicated_lines  = | union of (file, line) over all duplicated block ranges |
duplicated_tokens = | union of stream indices inside duplicated blocks |
duplicated_blocks = number of clone groups (maximal sequences with ≥ 2 occurrences)

Duplication % = duplicated_lines / lines_of_code * 100
```

where `lines_of_code` is the sum of Radon `sloc` over the **successfully tokenized files only** (`duplication.py:616-629`), and the density is `0.0` when `lines_of_code == 0`. `calculate()` returns the density (`duplication.py:210-214`).

## 6. Scope and Completeness (ADR-0001)

- **`scope = "single_file"`** → `completeness: "not_applicable"`, density `None`, with the human-readable reason "Duplication compares token streams across the analyzed files — not applicable to a single-file input." (`duplication.py:105-122`) — a single file cannot be compared against itself, so no value is fabricated.
- **`scope = "project"`** → `completeness: "full"` when every file tokenized; `"partial"` with a `reason` listing files that raised `TokenError`/`IndentationError`/`SyntaxError` (`duplication.py:140-151`). Failed files are excluded from both the token stream **and** the line-count denominator (`duplication.py:216-242`) — never fabricated.

## 7. Documented Divergences from SonarQube

- **Tokenizer:** SonarQube uses the Python analyzer's grammar-based tokenizer; CodeInsight uses stdlib `tokenize`. Token sets are close but not identical (f-strings, operators, string prefixes split differently), so block boundaries can differ by a few tokens.
- **Detector:** SonarQube uses a suffix-tree detector; CodeInsight uses a rolling-hash matcher with maximal expansion. Both find maximal repeats; exact boundary handling may differ slightly.
- **Lines counting:** every physical line of a duplicated block's range is counted, including comment/blank lines *inside* the block (SonarQube does the same).
- **Denominator:** SonarQube's density uses `ncloc`; CodeInsight uses Radon's `sloc` — the same definition (non-comment, non-blank).
- **Thresholds:** defaults 100 tokens / 10 lines mirror SonarQube but are exposed as engine constants (`duplication.py:76-77`).
- **Clone types:** Type-1 (exact) only by default; Type-2 requires identifier/literal normalization; Type-3/Type-4 out of scope for a token-based metric.

## 8. Unit Tests

`backend/analysis/test/test_duplication.py` (555 lines):

- single-file input → `not_applicable` with reason
- exact cross-file copy → blocks=1, lines=10, tokens=48, loc=12, density `10/12*100`
- no duplication → 0
- 100% entire-file duplication
- whitespace/formatting differences still match
- identifier rename **not** detected (Type-1 semantics)
- token and line threshold boundaries (below/at min)
- default 100-token threshold rejects a 24-token fixture, detects a 123-token / 30-line clone
- unparsable file → `partial` with reason; empty file list → 0.0
- engine registered in `ENGINE_REGISTRY`; `MetricDefinition` seeded (display name "Duplication %", category "Code Health", `higher_is_better False`, `supports_llm True`)

Integration coverage also exists in `test_api_analysis.py:232-239` and `test_service.py:1234, 1348, 1393-1456`.

## 9. References

- SonarQube "Metric definitions": [docs.sonarsource.com](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition)
- SonarQube core duplication engine API: [javadocs.sonarsource.org — org.sonar.duplications](https://javadocs.sonarsource.org/3.1/apidocs/org/sonar/duplications/token/package-summary.html)
- PMD CPD — token-based copy/paste detector: [pmd.github.io](https://pmd.github.io/pmd/pmd_userdocs_cpd.html)
- Bellon, Koschke, Antoniol, Krinke, Merlo, *Comparison and Evaluation of Clone Detection Tools*, IEEE TSE 33(9), 2007
- Kamiya, Kusumoto, Inoue, *CCFinder*, IEEE TSE 28(7), 2002
- Roy & Cordy, *A Survey on Software Clone Detection Research*, 2007
- Python `tokenize` module: [docs.python.org](https://docs.python.org/3/library/tokenize.html)
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight ADR-0002, standalone analyzer: [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- Engine: `backend/analysis/engines/duplication.py` · LOC denominator: `backend/analysis/engines/loc.py` · Tests: `backend/analysis/test/test_duplication.py`
- Registration: `MetricDefinition` key `DUPLICATION`, display name "Duplication %", category "Code Health" (`backend/analysis/migrations/0008_seed_duplication.py:11-25`)
