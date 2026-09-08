# Duplication

## 1. Overview

**Duplication** is a code-health metric that measures how much of the analyzed codebase is repeated — the classic copy-paste ("clone") signal. CodeInsight follows the **SonarQube semantics** for this metric family: detection is **token-based** (source is tokenized, repeated token sequences are located, and the lines covered by those sequences are counted), and the headline value is a **lines-based ratio**: duplicated lines divided by the total number of (physical) lines.

In CodeInsight the metric is **fully hand-implemented**: a custom tokenizer on the standard `tokenize` module plus a hand-rolled **Rabin–Karp rolling-hash** matcher. There is no duplication library — `radon` is used only indirectly, for the physical-line denominator via the existing LOC engine.

## 2. Purpose

Duplicated code is a maintenance risk: a bug in a duplicated block must be fixed in every copy, and refactoring one copy without the others silently diverges behavior. The metric is interpreted together with the other maintainability metrics (LOC, complexity, coupling/cohesion) as a signal of copy-paste behavior, not as a standalone verdict.

## 3. Reference Definition (SonarQube)

SonarQube defines five duplication measures on its "Metric definitions" page ([docs.sonarsource.com — Metric definitions](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition)):

- `duplicated_blocks` — number of duplicated blocks of lines.
- `duplicated_files` — number of files involved in duplications.
- `duplicated_lines` — number of lines involved in duplications.
- `duplicated_lines_density` — **Duplicated lines (%)** — number of lines involved in duplications divided by the number of lines (`duplicated_lines_density = duplicated_lines / lines * 100`).
- `duplicated_tokens` — number of tokens involved in duplications.

The percentage is a **lines-based ratio, not a token-based ratio**:

```text
Duplicated lines (%) = duplicated_lines / lines * 100
```

The denominator is SonarQube's `lines` measure — **physical lines** (including comment and blank lines, "the number of physical lines", see the [current metric definitions](https://docs.sonarsource.com/sonarqube-server/2025.4/user-guide/code-metrics/metrics-definition.md#duplications)) — so a file whose lines all lie inside duplicated blocks reports at most `100%`. In CodeInsight terms `lines` maps to Radon's `loc` (physical line count) produced by the existing LOC engine (`radon.raw.analyze`).

SonarQube's detection is token-based, computed by the platform core module `org.sonar.duplications` (tokenization in `org.sonar.duplications.token`, clone detection via a suffix-tree detector in `org.sonar.duplications.detector.suffixtree`); language plugins only supply the token stream. Default thresholds: a duplicated block needs at least **100 successive duplicated tokens** and must span a minimum of **10 lines** (both configurable).

Clone taxonomy (Bellon et al. 2007; Roy & Cordy 2007): **Type-1** = identical except whitespace/layout/comments; **Type-2** = additionally renamed identifiers/changed literals; **Type-3** = gapped modifications; **Type-4** = semantic clones. SonarQube and PMD CPD detect Type-1 (and near-exact) clones by default; CodeInsight does the same.

## 4. Implementation Basis: Manual (no library)

The duplication engine is **100% hand-implemented** — there is no maintained Python library that implements SonarQube-style token-based duplication with a duplication-density output (pydedupe is unrelated record-linkage software; pylint's R0801 is a line-similarity checker with no percentage/token counts; ruff has no clone rule; radon has no duplication detection; flay is AST-based, unmaintained and not SonarQube-compatible; jscpd is a Node.js CLI with jscpd's own semantics).

- Engine file: `backend/analysis/engines/duplication.py`
- **Tokenization:** the Python standard-library `tokenize` module (`_tokenize_source`) — not a grammar tokenizer.
- **Matching:** a hand-rolled **Rabin–Karp rolling hash** (`_window_hashes`) with per-token `zlib.crc32` hashes, plus direct comparison to verify hash collisions.
- **Explainability:** a best-effort `ast.parse` per analyzed file (`_parse_source`) feeds the region-attribution helpers (`_build_index`/`_region_attribution`) that give every duplicated occurrence its `entity`/`kind` evidence.
- **Canonicalization:** `_canonicalize_clones` drops rotated and inner groups whose occurrences are already covered by an earlier kept group.
- **Denominator:** Radon's `loc` (physical lines) via the existing LOC engine — `from radon.raw import analyze` (`loc.py`), `result.loc`, delegated in `_lines_of_code`.
- Runtime dependencies: `radon==6.0.1` is the only analysis dep; no tokenizer/duplication library (`backend/requirements.txt`).

## 5. Calculation Steps in CodeInsight

**Tokenization** (`_tokenize_source`): each file is read once and tokenized with `tokenize`; the comparison stream **drops** `COMMENT`, `NL`, `ENCODING`, `ENDMARKER` (comments and blank lines are invisible to matching) and **keeps** `NAME`, `OP`, `NUMBER`, `STRING`, keywords, `NEWLINE`, `INDENT`, `DEDENT` so statement structure is preserved. `INDENT`/`DEDENT` are normalized to the markers `"<INDENT>"`/`"<DEDENT>"`; string prefixes are stripped; all other token texts are kept as-is. This yields **Type-1 (exact) clone detection by default** — identifier renames break a match, exactly like SonarQube/CPD defaults. The same text is handed to `_parse_source` so each duplicated region can later be attributed to a named construct. The streams of all analyzed files are concatenated into one stream of `{text, file, line}` triples; on a `single_file` input that stream holds the one file alone, so only repeats **inside** the file can match.

**Detection** (`_find_clones`): rolling-hash buckets of `min_tokens`-sized windows (default 100; `_window_hashes`) are built; overlapping same-file windows are dropped (`_drop_overlapping_windows`); hash collisions are verified by direct token comparison and matches are expanded left/right to **maximal repeated sequences** (`_maximal_group`). A clone group is kept only if **every occurrence spans at least `min_lines` (default 10) distinct physical lines** (`_meets_line_minimum`; `_block_end_line` steps over trailing INDENT/DEDENT). Every occurrence needs **two or more non-overlapping matches**, which is what makes an intra-file repeat real evidence rather than a fabricated number: a lone function with no second copy never self-matches.

**Canonicalization** (`_canonicalize_clones`): a periodic file — e.g. twelve byte-identical copies of one 72-line unit — also matches in *rotated* windows that start inside a copy and run over the boundary into the next (lines 49–120, 50–121, 53–125, …), producing dozens of equal-length clone groups that add no new duplicated content. Groups are processed longest-first (ties by earliest start); a group whose **every** occurrence already lies inside the token intervals covered by kept groups for that file is dropped. Coverage is tracked per file, so two genuinely independent duplicated chunks stay separate. `duplicated_blocks` therefore counts the **maximal** repeated sequences only.

**Measures** (`_analyze_project`):

```text
duplicated_lines  = | union of (file, line) over all duplicated block ranges |
duplicated_tokens = | union of stream indices inside duplicated blocks |
duplicated_blocks = number of canonical clone groups (maximal sequences
                    with ≥ 2 occurrences, not covered by an earlier group)

density = duplicated_lines / lines_of_code * 100
```

where `lines_of_code` is the sum of Radon `loc` (physical lines) over the **successfully tokenized files only** (`_lines_of_code`), and the density is `0.0` when `lines_of_code == 0`. `calculate()` returns the density.

**Explainable block findings** — the user-facing answer to "what was repeated, and where". Every occurrence row in `detail["blocks"]` carries, besides `file`/`start_line`/`end_line`, the clone-group fields (`group` = which duplicated block, `ordinal` = copy number inside it, `copies` = total copies — the rows of one group are the copies of one another) and the AST-attribution fields:

```json
{
  "file": "a.py",
  "start_line": 10,
  "end_line": 23,
  "group": 0,
  "copies": 2,
  "ordinal": 1,
  "entity": "duplicated",
  "entity_type": "function",
  "class_name": null,
  "kind": "function"
}
```

- `entity`/`entity_type`/`class_name` name the nearest containing named construct — the whole duplicated function/method/class when its header is inside the region, otherwise the innermost function/method/class that contains it. Method occurrences carry their owning class in `class_name`; a region at module level reports `entity: null`, `entity_type: "module"`.
- `kind` says what the region itself is: `"function"`/`"method"`/`"class"` for a whole named construct, a construct label for a single contained statement (`for loop`, `while loop`, `if/elif/else`, `try/except`, `with block`, `assignment`, …), or `"statements"` for a sequence of statements (a whole duplicated file or a duplicated body whose headers differ — the copies then keep their own enclosing entity names).
- The attribution is **best-effort**: region boundaries are token lines, and a maximal repeat can bridge from one construct into a neighbour (e.g. two copies of a function whose *name* differs match from the header's closing parens onward), so the reported `kind`/`entity` are labels over the region while `start_line`/`end_line` stay authoritative. Files that tokenize but fail `ast.parse` still join detection (their duplicated lines are real); their occurrences report the four attribution fields as `null` and the files are listed in `detail["unattributed_files"]`, so the UI can explain the missing names instead of silently showing dashes.

## 6. Scope and Completeness (ADR-0001)

- **`scope = "single_file"`** → the file is **self-compared**: the analysis runs over the file's own token stream, so only repeated code **inside** the file is reported (e.g. one function copied twice within the file — both occurrences are counted). `completeness` is `"full"` when the file tokenizes and the density is a real value: `0.0` when the file holds no repeated region (a lone function never self-matches, so nothing is fabricated), up to `100.0` for a fully duplicated file. `"partial"` with a `reason` when the file fails to tokenize. This replaces the earlier blanket `not_applicable` — an intra-file repeat is real evidence, exactly as SonarQube counts duplicated blocks inside a single file.
- **`scope = "project"`** → every file joins the comparison stream, so both **cross-file** copies and **intra-file** repeats count. `completeness: "full"` when every file tokenized; `"partial"` with a `reason` listing files that raised `TokenError`/`IndentationError`/`SyntaxError` (the failures are collected and the `reason` assembled in `_analyze_project`). Failed files are excluded from both the token stream **and** the line-count denominator — never fabricated.

## 7. Documented Divergences from SonarQube

- **Tokenizer:** SonarQube uses the Python analyzer's grammar-based tokenizer; CodeInsight uses stdlib `tokenize`. Token sets are close but not identical (f-strings, operators, string prefixes split differently), so block boundaries can differ by a few tokens.
- **Detector:** SonarQube uses a suffix-tree detector; CodeInsight uses a rolling-hash matcher with maximal expansion. Both find maximal repeats; CodeInsight additionally canonicalizes the raw groups (`_canonicalize_clones`) so rotated windows of a periodic file do not multiply `duplicated_blocks`.
- **Lines counting:** every physical line of a duplicated block's range counts toward `duplicated_lines`, including comment/blank lines *inside* the block — the "lines involved in duplications" reading of SonarQube's measure.
- **Denominator:** SonarQube's documented formula divides `duplicated_lines` by its `lines` measure (physical lines); CodeInsight uses Radon's `loc` (physical lines over the successfully tokenized files), so the density stays within `[0, 100]`.
- **Explainability:** CodeInsight adds per-occurrence entity/kind attribution (`entity`/`entity_type`/`class_name`/`kind` + clone-group fields) that SonarQube's measures do not expose; when a file fails to parse, its blocks keep the duplicated-line evidence but report null attribution with an `unattributed_files` note instead of guessing.
- **Thresholds:** defaults 100 tokens / 10 lines mirror SonarQube but are exposed as engine constants (`MIN_TOKENS`/`MIN_LINES`).
- **Clone types:** Type-1 (exact) only by default; Type-2 requires identifier/literal normalization; Type-3/Type-4 out of scope for a token-based metric.
- **Single-file scope:** CodeInsight analyzes a lone `.py` by self-comparison so intra-file copies are reported (this used to be the `not_applicable` case; the amendment is recorded in ADR-0001). SonarQube likewise counts duplicated blocks inside a single analyzed file — the value is only ever backed by two or more real, non-overlapping occurrences.

## 8. Unit Tests

`backend/analysis/test/test_duplication.py`:

- single-file input with no internal repetition → `completeness: full`, density `0.0`, no fabricated blocks
- single-file input with one function copied twice inside it → blocks=1, two occurrences in the same file, lines=10, tokens=48, physical lines=11, density `10/11*100` (the blank separator is in the denominator, not duplicated)
- single unparsable file → `partial` with reason, density `0.0`
- exact cross-file copy → blocks=1, lines=10, tokens=48, loc=12, density `10/12*100`
- no duplication → 0
- 100% entire-file duplication
- whitespace/formatting differences still match
- identifier rename **not** detected (Type-1 semantics)
- token and line threshold boundaries (below/at min)
- default 100-token threshold rejects a 24-token fixture, detects a 123-token / 30-line clone
- unparsable file in a project → `partial` with reason; empty file list → 0.0
- canonicalization (`CanonicalizationTest`): one unit repeated six times in a file → `duplicated_blocks` `1` with six occurrences (rotated windows are dropped); nested inner repeats inside a duplicated chunk add no extra block
- parse-failure attribution (`ParseFailureAttributionTest`): a tokenizable-but-unparseable duplicated file keeps real duplication (`full`), is listed in `unattributed_files`, and its blocks carry null entity/kind
- explainable block detail (`ExplainableBlockDetailTest`): whole-function copies carry `entity`/`entity_type`/`kind` + the clone-group fields; two renamed function copies are attributed to each own name (`alpha`/`beta`, kind `function`); a loop copied twice inside one function → kind `for loop` under the enclosing function; methods copied within one class → kind `method` with `class_name`; a whole class copied across files → kind `class`; repeated module-level statements → `entity null`, `entity_type "module"`, kind `statements`
- `test_detail_contract.py` pins the block fields (`group`/`copies`/`ordinal`/`entity`/`entity_type`/`class_name`/`kind`) and their semantics for every duplicated occurrence
- engine registered in `ENGINE_REGISTRY`; `MetricDefinition` seeded (display name "Duplication", category "Code Health", `higher_is_better False`, `supports_llm True`)

Integration coverage: single-file self-comparison end-to-end in `test_service.py` (`test_duplication_single_file_reports_internal_copies` — a 30-line function copied twice in one file reports density `60/61*100`, the blank separator staying in the denominator) and `test_api_analysis.py` (`test_not_applicable_metric_is_reported_gracefully` — duplication returns a real value on a lone file while `CYCLIC` stays `not_applicable`), plus the project-scope duplication run in `test_service.py`.

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
- Registration: `MetricDefinition` key `DUPLICATION`, display name "Duplication", category "Code Health" (`backend/analysis/migrations/0008_seed_duplication.py:11-25`)
