# Lack of Cohesion of Methods (LCOM)

## 1. Overview

**Lack of Cohesion of Methods (LCOM)** is a design-quality metric from the Chidamber–Kemerer object-oriented metrics suite (1994). It measures how unrelated the methods of a class are: methods are cohesive when they share instance attributes (they work on the same data); a class whose methods share little or no data is a sign that several unrelated responsibilities were merged into one class.

CodeInsight implements the **original LCOM1** definition of Chidamber & Kemerer at **class level**, over the `self.<attr>` accesses inside each method body. The engine also reports the `P` and `Q` pair counts behind the value, plus a project total and average.

## 2. Reference Definition

Chidamber & Kemerer, *"A Metrics Suite for Object Oriented Design"*, IEEE TSE 20(6), 1994, define LCOM1 as follows:

> LCOM = |P| − |Q|, if |P| > |Q|, and 0 otherwise,
> where P is the set of method pairs that share **no** instance variable, and Q the set of method pairs that share at least one instance variable.

The intuition: a class should represent one cohesive abstraction. If most method pairs share no data, the class is probably doing several jobs and should be split.

## 3. Formula

```text
P = number of method pairs sharing NO instance attribute
Q = number of method pairs sharing AT LEAST ONE instance attribute

LCOM1 = max(P - Q, 0)
```

with the convention that a class with fewer than 2 methods has `LCOM = 0` (no pairs exist). The `max(..., 0)` clamp means LCOM is never negative — a perfectly cohesive class (all pairs share data) scores 0.

An instance attribute means an attribute accessed through `self.<attr>` inside a method body: `self.name`, `self.total`, … Accesses on other objects (`user.name`, `repository.delete()`) are **not** class attributes and are ignored.

## 4. Implementation Basis: Manual (no library)

LCOM is **fully hand-implemented** on the Python standard library `ast` module — no Radon, no networkx, no external library.

- Engine file: `backend/analysis/engines/lcom.py`
- Imports: `ast` only (`lcom.py:1`) plus `pathlib`.
- AST walking: `_LCOMVisitor(ast.NodeVisitor)` (`lcom.py:195-303`).
- Pair counting: `_LCOMClassContext.calculate_lcom` (`lcom.py:150-191`), including the `max(..., 0)` clamp (`lcom.py:186-189`) and the `< 2 methods → (0, 0, 0)` short-circuit (`lcom.py:157-158`).
- Attribute collection: `_collect_instance_attributes` walks each method body and keeps only `ast.Attribute` nodes whose value is `ast.Name("self")` (`lcom.py:277-303`).

## 5. Calculation Steps in CodeInsight

1. For every class in every analyzed file, list its methods (excluding dunder machinery where not relevant to the count).
2. For each method, collect the set of `self.<attr>` attribute names used in its body (`lcom.py:277-303`).
3. For every unordered pair of methods, compare their attribute sets: no common attribute → count in P; at least one common attribute → count in Q (nested pair loop, `lcom.py:163-184`).
4. `LCOM1 = max(P - Q, 0)` (`lcom.py:186-189`).

The scalar `calculate()` result is the **sum of all class LCOM values** in the input (`lcom.py:28-42`). Detailed output (`calculate_detailed`, `lcom.py:76-88`) is grouped `files → classes[{name, lcom, p, q, method_count, methods: [{name, lineno, endline, attributes}], lineno, endline}]` plus `total`, `average`, `class_count`, `scope` and `completeness`.

## 6. Scope and Completeness (ADR-0001)

LCOM counts only **within-class** `self`-attribute pairs, so the value for a class is complete from that class's own AST alone — nothing outside the class is observed.

- LCOM reports `completeness: "full"` at **any** scope (`lcom.py:83`): a single-file input yields the same per-class values as a project input (comment at `lcom.py:79-82`, per ADR-0001).

## 7. Limitations

- **LCOM1, not the variants.** CodeInsight implements the original LCOM1. Later variants (LCOM2–LCOM4, Henderson-Sellers' LCOM*, the "lack of cohesion" definitions used by tools like SonarQube's LCOM4 or IntelliJ's LCOM) count differently — e.g. LCOM2 sums `(m(μ) − |P|)` per attribute and clamps differently — so CodeInsight values are not directly comparable to tools that use another variant.
- **`self`-attribute approximation.** Only literal `self.<attr>` accesses count. Attributes stored via `setattr`, class-level `__init__` helpers, or accessed through other references to the instance are missed — the same name-based approximation as the other hand-rolled engines.
- **Zero is a target, not a verdict.** LCOM = 0 for both a class with < 2 methods and a perfectly cohesive class; the metric says nothing about size or importance.

## 8. Unit Tests

`backend/analysis/test/test_lcom.py` asserts hand-computed values (ADR-0002 — no reference tool is ever invoked):

- class with no methods → 0 (`:28`)
- class with one method → 0 (`:48`)
- all method pairs share an attribute → P=0, Q=3, LCOM=0 (`:70`)
- no method pair shares an attribute → P=3, Q=0, LCOM=3 (`:108`)
- mixed case → P=5, Q=1, LCOM=4 (`:146`)
- negative result is clamped to 0 (`:187`)
- attributes on external objects (`user.name`) are ignored → LCOM=1 (`:225`)
- `scope`/`completeness` is `full` on both scopes (`:250`)

## 9. References

- Chidamber, S. R. & Kemerer, C. F., *A Metrics Suite for Object Oriented Design*, IEEE TSE 20(6), 1994.
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight ADR-0002, standalone analyzer: [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- Engine: `backend/analysis/engines/lcom.py` · Tests: `backend/analysis/test/test_lcom.py`
- Registration: `MetricDefinition` key `LCOM`, display name "Lack of Cohesion of Methods", category "Design Quality" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:80-88`)
