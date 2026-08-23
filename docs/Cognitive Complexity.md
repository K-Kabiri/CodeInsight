# Cognitive Complexity

## 1. Overview

**Cognitive Complexity** is a software metric designed to estimate how difficult a piece of code is to understand from a human reader's perspective. It was introduced by **SonarSource** as a complement to Cyclomatic Complexity: while Cyclomatic Complexity counts independent execution paths, Cognitive Complexity weights the constructs that actually cost a reader mental effort — branching, nesting, breaks in linear flow.

Unlike the other three "Complexity & Size" metrics (LOC, Cyclomatic Complexity, Halstead), Cognitive Complexity in CodeInsight is **hand-implemented**: a custom `ast.NodeVisitor` that walks each function's AST and applies the SonarSource Cognitive Complexity model.

## 2. Purpose

A higher Cognitive Complexity indicates more complicated control flow, deeper nesting, more branches and more interruptions in the linear flow of the code — i.e. increased mental effort to understand it. The metric is therefore an indicator of maintainability and readability, used to flag code that may be hard to understand even when its Cyclomatic Complexity is modest.

## 3. Reference Definition

The implementation follows the **SonarSource Cognitive Complexity model** (engine docstring `cognitive.py:8-44`; catalog description "SonarSource cognitive complexity", migration `0005_seed_canonical_catalog.py:41-46`). The model is built on four concepts:

1. **Structural increments** — each control-flow construct adds a base amount that grows with nesting depth.
2. **Nesting increments** — the deeper a construct is nested, the more each structural increment costs.
3. **Fundamental increments** — constructs that break linear flow (`break`, `continue`, recursion).
4. **Logical sequences** — each `and`/`or` boolean sequence adds one point.

The canonical formulation (per the SonarSource specification and CodeInsight's previous doc): `increment = 1 + current_nesting_level`.

## 4. Implementation Basis: Manual (no library)

Cognitive Complexity is **fully hand-implemented** on the Python standard library `ast` module — it is the only one of the four Complexity & Size metrics not delegated to Radon.

- Engine file: `backend/analysis/engines/cognitive.py`
- `tree = ast.parse(...)` per file (`cognitive.py:98`)
- `_CognitiveComplexityVisitor(ast.NodeVisitor)` (`cognitive.py:177`) walks functions with an independent nesting context per function (functions pushed/popped on `_function_stack`, `cognitive.py:236-260`; nested functions get a fresh context)

## 5. Calculation Steps in CodeInsight

Per function, the visitor applies the SonarSource rules:

| Construct | Increment | Code reference |
|---|---|---|
| `if` / `elif` / `else` | structural `1 + nesting` (elif/else with nesting increment) | `_add_structural` `cognitive.py:285`; elif `:340-349`, else `:384-391` |
| `for` / `while` / `async for` | structural `1 + nesting` | `_add_structural` |
| `except` handlers | structural `1 + nesting` each | `cognitive.py:455-494` |
| `match` / `match_guard` | structural `1 + nesting` each | `cognitive.py:567-588`, `:597-603` |
| conditional expression (`a if b else c`) | +1 flat | `cognitive.py:498-515` |
| `and` / `or` sequences | +1 flat per BoolOp node | `visit_BoolOp` `cognitive.py:518-534` |
| `break` / `continue` | +1 flat each | `cognitive.py:537-549`, `:552-564` |
| recursion | +1 flat (direct calls only: callee is a bare `Name` equal to the current function name) | `cognitive.py:611-630`, `_is_recursive_call` `:632-644` |
| `try` / `finally` | 0 (nothing added; only `except` handlers count) | `cognitive.py:455-494` |

Boolean-sequence semantics are reproduced through Python's AST shape: Python flattens same-operator chains into one `BoolOp` node (`a and b and c` → 1 point), but nests mixed operators (`a and b or c` → 2 points), matching SonarSource's "one point per logical sequence".

Per-function detail `_finish_function` (`cognitive.py:214-233`) emits `name`, `type` (`method` inside a class, else `function`), `complexity`, `max_nesting`, `lineno`/`endline`, optional `classname`, and **per-contribution records** `{"type", "increment", "nesting", "lineno", "reason"}` (`cognitive.py:142-163`) — purpose-built so the reporting and AI layers can explain how the score was produced (engine docstring `cognitive.py:42-43`).

Aggregation (`cognitive.py:83-89`): `{"metric": "Cognitive Complexity", "total", "average", "function_count", "files"}`; the scalar `calculate()` returns `total`, the sum of per-function scores (`cognitive.py:51-54, 75`). The `scope` parameter is ignored (not a dependency-based metric; no `scope`/`completeness` fields).

## 6. Scope and Completeness

Cognitive Complexity is applicable at **any scope** and always complete: each function's score derives from that function's own AST alone. No `scope`/`completeness` keys are emitted.

## 7. Limitations

- **Direct recursion only.** `_is_recursive_call` (`cognitive.py:632-644`) requires the callee to be a bare `Name` equal to the current function name; `self.method()` / attribute-based recursion is **not** detected, so such recursion adds no increment.
- **Nesting is per function.** Maximum nesting is tracked per function with an independent context; nesting across function boundaries is not accumulated.

## 8. Unit Tests

`backend/analysis/test/test_cognitive.py` (1008 lines — the largest suite):

- empty/simple function → 0 (`:36`, `:44`); `if` +1 (`:58`); `if/else` +2 (`:72`); `if/elif/else` +3 (`:90`)
- nesting math: nested if 1+2=3 (`:112`); deep nesting 1+2+3=6 (`:129`); nested elif/else = 2 (nesting increment) (`:146`, `:166`); `max_nesting` reported (`:186`)
- loops: `for`/`while` +1 (`:206`, `:220`); nested loops 1+2=3 (`:234`); `async for` +1 (`:251`)
- boolean sequences: single and/or → 1 contribution (`:283`, `:299`); mixed `a and b or c` → 2 (`:315`); parenthesized `(a and b) or (c and d)` → 3 (`:332`)
- `except` +1 (`:358`); multiple handlers counted (`:376`); `try/finally` → 0 (`:396`)
- ternary +1 (`:413`); nested ternary 2 (`:426`); `break`/`continue` +1 (`:442`, `:460`)
- recursion +1 (`:479`); non-recursive call free (`:497`); recursion inside nested condition (`:510`)
- `match` +1 (`:527`); match guard +2 (`:546`); async function (`:564`)
- multiple functions independent (`:593`); nested function has independent nesting (`:639`)
- class methods: `type=method`, `classname="User"` (`:680`); multi-file aggregation (`:729`); average/function_count (`:769`, `:801`); contribution records with type/increment/lineno/nesting (`:863`, `:897`, `:934`, `:960`, `:980`)

## 9. References

- SonarSource, *Cognitive Complexity — A new way of measuring understandability*: [sonarsource.com](https://www.sonarsource.com/blog/cognitive-complexity/)
- Engine: `backend/analysis/engines/cognitive.py` · Tests: `backend/analysis/test/test_cognitive.py`
- Registration: `MetricDefinition` key `COGNITIVE`, display name "Cognitive Complexity", category "Complexity & Size" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:38-46`)
