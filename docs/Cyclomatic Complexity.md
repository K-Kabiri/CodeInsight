# Cyclomatic Complexity

## 1. Overview

**Cyclomatic Complexity** is a software metric that measures the number of linearly independent paths through a program's control-flow graph. It was introduced by Thomas J. McCabe in 1976. In CodeInsight it is calculated with **Radon's `cc_visit` implementation** — not hand-implemented — at the **block level**, so complexity is reported separately for functions, methods and classes. Each analyzed block also carries Radon's complexity **rank** (letter grade A–F).

## 2. Purpose

Cyclomatic Complexity measures the structural complexity of program control flow: more decision points mean more possible execution paths, and therefore code that is harder to understand, harder to test and riskier to modify. It is analyzed together with the other CodeInsight metrics (LOC, Cognitive Complexity, Halstead Volume, coupling, cohesion, Code Smells) rather than as a standalone quality verdict.

## 3. Standard Definition

McCabe's classical definition, for a connected control-flow graph:

```text
M = E - N + 2

M = Cyclomatic Complexity
E = number of edges
N = number of nodes
```

Each decision point (`if`, `for`, `while`, `except`, boolean operator `and`/`or`, …) adds one independent path. Radon's implementation of the metric ("each analyzed block starts with a base complexity of 1", engine docstring `cyclomatic.py:17-19`) is the reference CodeInsight uses; the catalog description cites "McCabe's cyclomatic complexity" (migration `0005_seed_canonical_catalog.py:27-32`).

## 4. Implementation Basis: Library (Radon)

Cyclomatic Complexity is **delegated to Radon** — it is *not* hand-implemented.

- `from radon.complexity import cc_rank, cc_visit` (`cyclomatic.py:3`)
- `blocks = cc_visit(source_code)` per file (`cyclomatic.py:83`)
- rank via `cc_rank(block.complexity)` (`cyclomatic.py:122`)

Radon's rank thresholds (verified against installed Radon 6.0.1): A = 1–5, B = 6–10, C = 11–20, D = 21–30, E = 31–40, F = 41+. Runtime dependency: `radon==6.0.1` (`backend/requirements.txt`).

## 5. Calculation Steps in CodeInsight

1. Per file, `cc_visit` returns Radon blocks (functions, methods, classes) with their complexity.
2. Per-block serialization `_serialize_block` (`cyclomatic.py:103-145`): `name`, `type` (`class` if the block has methods, `method` if `is_method`, else `function` — `cyclomatic.py:110-120`), `complexity`, `rank`, `lineno`/`endline`/`col_offset`, plus `classname`, `is_method`, `real_complexity` and nested `methods` for classes.
3. Aggregation (`cyclomatic.py:53-64`): the project `total` sums **top-level blocks only** — Radon's class complexity already includes its methods, so methods are not double-counted; `average = total / len(all_complexities)` is over all blocks.
4. Scalar `calculate()` returns `result["total"]` (`cyclomatic.py:26, 58`).

The `scope` parameter is ignored: the metric is not dependency-based, ADR-0001 does not apply, and no `scope`/`completeness` fields are emitted.

## 6. Scope and Completeness

Cyclomatic Complexity is applicable at **any scope** and always complete: each block's complexity derives from that block's own AST alone. No `scope`/`completeness` keys are emitted.

## 7. Limitations

- **Control-flow only.** The metric counts paths, not readability — two equally complex functions can differ wildly in how hard they are to *understand*. Cognitive Complexity exists precisely to cover that gap.
- **Rank grades are Radon's.** The A–F letter grades are Radon's mapping of complexity ranges, not an official McCabe scale.

## 8. Unit Tests

`backend/analysis/test/test_cyclomatic.py` (431 lines):

- empty file → 0 (`:34`); simple function → 1 (`:42`)
- `if` adds 1 → 2 (`:55`); `if/else` stays 2 (else is free) (`:70`); `elif` adds 1 → 3 (`:86`)
- `for`/`while` add 1 (`:103`, `:117`); `except` adds 1 → 2 (`:131`); `a and b` adds 1 → 3 (`:151`)
- nested ifs counted (`:170`); multiple functions reported independently (`:190`); async functions (`:239`)
- class + 2 methods: `type: class` with nested `methods` (`:263`); rank "A" for complexity 2 (`:310`)
- multi-file aggregation total 5 (`:334`); average 1.5 over blocks (`:373`); `lineno`/`endline` preserved with `endline >= lineno` (`:406`)

## 9. References

- Thomas J. McCabe, *A Complexity Measure*, IEEE Transactions on Software Engineering, 2(4), 1976.
- Radon documentation — cyclomatic complexity: [radon.readthedocs.io](https://radon.readthedocs.io/en/stable/intro.html)
- Engine: `backend/analysis/engines/cyclomatic.py` · Tests: `backend/analysis/test/test_cyclomatic.py`
- Registration: `MetricDefinition` key `CYCLOMATIC`, display name "Cyclomatic Complexity", category "Complexity & Size" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:24-32`)
