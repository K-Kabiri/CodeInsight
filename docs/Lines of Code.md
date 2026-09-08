# Lines of Code (LOC)

## 1. Overview

**Lines of Code (LOC)** is a source-code size metric that measures the physical size of Python source files. In CodeInsight, LOC is the raw physical line count (`loc` in Radon's terms) summed across all analyzed files, and it is computed with the `radon.raw.analyze` function — **not** with a hand-written line counter.

Alongside the headline LOC value, the engine stores the full set of Radon raw source-code metrics per file (source LOC, logical LOC, comments, blank lines, multiline strings), which are used elsewhere in the project (for example as the denominator of the Duplication density).

## 2. Purpose

LOC measures the size of the analyzed Python codebase and provides context for interpreting the other metrics: a large module that scores badly on Cyclomatic Complexity, Cognitive Complexity, Halstead Volume or Code Smells is a different signal than a small one. LOC alone does not determine code quality — a larger codebase is not necessarily a lower-quality one.

## 3. Reference Definition

CodeInsight follows **Radon's raw metric definition** (engine docstring, `loc.py:53`; catalog description "Source lines of code per Radon's raw metric definition", migration `0005_seed_canonical_catalog.py:14-18`). Radon's `analyze` function returns a namedtuple with these fields (per Radon 6.0.1 documentation):

| Field | Meaning |
|---|---|
| `loc` | **LOC** — total physical lines of the file (the headline value) |
| `lloc` | Logical LOC — statements (control flow, assignments, …) |
| `sloc` | Source LOC — `loc` minus blanks, comments and multiline strings |
| `comments` | Comment lines |
| `multi` | Lines of multiline strings |
| `single_comments` | Standalone comment lines |
| `blank` | Blank lines |

with the invariant `sloc + blanks + multi + single_comments = loc`. Radon's documentation: [radon.readthedocs.io — Introduction to Code Metrics](https://radon.readthedocs.io/en/stable/intro.html).

## 4. Implementation Basis: Library (Radon)

LOC is **delegated to the Radon library** — it is *not* hand-implemented.

- `from radon.raw import analyze` (`loc.py:4`)
- Called as `result = analyze(source_code)` per file (`loc.py:126`)
- All seven raw fields are taken directly from the returned namedtuple (`loc.py:128-135`)

Runtime dependency: `radon==6.0.1` (pinned in `backend/requirements.txt`).

## 5. Calculation Steps in CodeInsight

1. For each analyzed `.py` file, read the source and call `radon.raw.analyze` (`loc.py:126`).
2. Per-file detail entry: `{"file": str(path), **metrics.to_dict()}` — the file path plus all seven Radon fields (`loc.py:78-83`).
3. Aggregation into `{"totals": {...}, "files": [...]}` (`loc.py:113-116`): the totals sum the seven fields across files (`loc.py:85-105`).
4. Derived metric: `comment_ratio = comments / loc`, guarded against division by zero (`loc.py:23-31`; totals version at `loc.py:107-111`).
5. Scalar `calculate()` returns `result["totals"]["loc"]` — the **physical LOC summed across files** (`loc.py:60`).

No per-function or per-class breakdown is produced (LOC is a file-level metric), and the `scope` parameter is ignored: LOC is not dependency-based, so ADR-0001 does not apply and no `scope`/`completeness` fields are emitted.

## 6. Scope and Completeness

LOC is applicable at **any scope** (`single_file` or `project`) and is always complete: the count for a file is derived from that file's own text alone. It emits no `scope`/`completeness` keys — ADR-0001 covers only dependency-based metrics (CBO, DIT, Instability, Cyclic, Duplication).

## 7. Limitations

- **Physical lines, not statements.** LOC counts physical lines, so formatting choices (one statement per line vs. several) change the value. The `lloc` field is available for a statement-based view, and `sloc` for the non-comment, non-blank view.
- **No language semantics.** LOC says nothing about what the lines do; it must be interpreted together with the complexity, coupling and code-health metrics.

## 8. Unit Tests

`backend/analysis/test/test_loc.py` (149 lines):

- empty file → 0 (`:31`)
- 3-statement file → 3 (`:39`)
- detailed shape contains `totals`/`files` and all 7 raw keys (`:53`)
- per-file entry carries the `file` path (`:79`)
- multi-file aggregation 1+2=3 with 2 file entries (`:106`)
- `comment_ratio` within [0, 1] (`:131`)

## 9. References

- Radon documentation — raw source metrics: [radon.readthedocs.io](https://radon.readthedocs.io/en/stable/intro.html)
- Engine: `backend/analysis/engines/loc.py` · Tests: `backend/analysis/test/test_loc.py`
- Registration: `MetricDefinition` key `LOC`, display name "Lines of Code", category "Complexity & Size", unit "lines" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:11-18`)
