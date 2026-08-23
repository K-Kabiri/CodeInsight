# Halstead Metrics

## 1. Overview

**Halstead Metrics** (Halstead software science) is a family of size-and-complexity measures introduced by Maurice H. Halstead in 1977. The measures are derived from counts of **operators** and **operands** in the source code:

```text
h1 = distinct operators      N1 = total operators
h2 = distinct operands       N2 = total operands
vocabulary = h1 + h2
length     = N1 + N2
```

In CodeInsight the metric is computed with **Radon's `h_visit` implementation** — not hand-implemented. The headline scalar is **Halstead Volume**, summed across all analyzed files; the detailed output also carries `calculated_length`, `difficulty`, `effort`, `time` and `bugs` per file and per function.

## 2. Purpose

Halstead Volume measures the "size" of the code in information-theoretic terms — how much information a reader must absorb. Along with difficulty and effort, it is used as a complexity signal together with the other CodeInsight metrics (LOC, Cyclomatic Complexity, Cognitive Complexity). Like LOC, it is a size-family metric: it must be interpreted in context, not as a standalone quality verdict.

## 3. Reference Definition

The metric family follows Halstead's software-science definitions via Radon. Radon computes the classic measures from operator/operand counts:

```text
vocabulary (η)        = h1 + h2
length (N)            = N1 + N2
volume (V)            = N * log2(η)
difficulty (D)        = (h1 / 2) * (N2 / h2)
effort (E)            = D * V
time (T)              = E / 18 seconds
bugs (B)              = V / 3000
```

The catalog description: "Halstead software-science metrics (volume, difficulty, effort) computed via Radon; the scalar value is the total Halstead Volume across all analyzed files" (migration `0005_seed_canonical_catalog.py:55-59`).

## 4. Implementation Basis: Library (Radon)

Halstead is **delegated to Radon** — it is *not* hand-implemented.

- `from radon.metrics import h_visit` (`halstead.py:3`)
- `result = h_visit(source_code)` per file (`halstead.py:80`); `total = result.total` (`halstead.py:81`)

Runtime dependency: `radon==6.0.1` (`backend/requirements.txt`).

## 5. Calculation Steps in CodeInsight

1. Per file, `h_visit` returns a `HalsteadReport` for the whole file plus per-function `(function_name, HalsteadReport)` tuples.
2. The engine surfaces `vocabulary = h1 + h2` and `length = N1 + N2` (`halstead.py:83-84`); the scalar metric is **Halstead Volume** = `total.volume` (`halstead.py:89`).
3. Per-file detail includes all components: volume, vocabulary, length, h1, h2, N1, N2, `calculated_length`, `difficulty`, `effort`, `time`, `bugs` (`halstead.py:86-110`).
4. Per-function entries via `_serialize_function` (`halstead.py:112-152`), which unpacks Radon's `(function_name, HalsteadReport)` tuples (`halstead.py:118-124`).
5. Aggregation (`halstead.py:55-61`): `total` = sum of per-file volumes; `average = total / len(files)` — **over files, not functions** (unlike Cyclomatic's block average).
6. Scalar `calculate()` returns `result["total"]` = the sum of per-file volumes (`halstead.py:26, 55`).

The `scope` parameter is ignored: not a dependency-based metric, so no `scope`/`completeness` fields are emitted (ADR-0001 covers only CBO, DIT, Instability, Cyclic, Duplication).

## 6. Scope and Completeness

Halstead is applicable at **any scope** and always complete: the counts derive from each file's own source alone. No `scope`/`completeness` keys are emitted.

## 7. Limitations

- **No line locations per function.** Radon's Halstead functions carry no line information; the cross-engine detail contract therefore pins only `name` as the minimum evidence for function records (`test_detail_contract.py:54-60`).
- **Average is per file.** The `average` aggregates file volumes, not function volumes — a project with many small functions and few files behaves differently than the Cyclomatic average. Read the two averages with their different units in mind.
- **Volume is size, not readability.** Two functions with equal volume can differ hugely in how understandable they are.

## 8. Unit Tests

`backend/analysis/test/test_halstead.py` (545 lines) — notable for **direct cross-validation against Radon**:

- empty file → volume 0 / average 0.0 (`:34`); empty project → 0/0.0/[] (`:54`)
- `calculate()` equals `h_visit(source).total.volume` (`:73`)
- every detailed field equals Radon's report fields — volume, vocabulary, length, h1, h2, N1, N2, calculated_length, difficulty, effort, time, bugs (`:89`)
- functions reported with names (`:164`); function metrics match Radon `h_visit().functions` tuples (`:198`); multiple functions have independent metrics (`:289`)
- multi-file aggregation: total = sum of Radon volumes, average = total/2 (`:359`, `:413`)
- file path reported (`:466`); file volume matches Radon (`:483`)
- internal consistency: vocabulary = distinct_operators + distinct_operands, length = total_operators + total_operands (`:501`)
- `calculate()` == `calculate_detailed()["total"]` (`:531`)

## 9. References

- Maurice H. Halstead, *Elements of Software Science*, Elsevier, 1977.
- Radon documentation — Halstead metrics: [radon.readthedocs.io](https://radon.readthedocs.io/en/stable/intro.html)
- Engine: `backend/analysis/engines/halstead.py` · Tests: `backend/analysis/test/test_halstead.py`
- Registration: `MetricDefinition` key `Halstead`, display name "Halstead Metrics", category "Complexity & Size" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:52-59`)
