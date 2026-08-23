# Depth of Inheritance Tree (DIT)

## 1. Overview

**Depth of Inheritance Tree (DIT)** is a design-quality metric from the Chidamber–Kemerer object-oriented metrics suite (1994). For a class, DIT is the length of the longest path from the class up to the root of its inheritance hierarchy. A deeper class inherits more behavior and state, which means more context the reader must hold and more places a change can break it.

In CodeInsight, DIT is computed at **class level** for every class defined in the analyzed Python files, over a **project-local** inheritance tree: the chain is measured only through base classes defined inside the analyzed input. An external or standard-library base (e.g. `django.db.models.Model`) terminates the chain, so the reported depth is the depth *within the analyzed project*.

## 2. Reference Definition

Chidamber & Kemerer, *"A Metrics Suite for Object Oriented Design"*, IEEE TSE 20(6), 1994:

> DIT of a class is the maximum length of the inheritance path from the class to the root of the inheritance tree.

The deeper a class is in the hierarchy, the more methods and attributes it inherits, making its behavior harder to predict and its testing more complex; DIT is therefore a coupling-to-inheritance signal.

## 3. Formula

```text
DIT(C) = 0                              if C has no base inside the analyzed project
DIT(C) = 1 + max(DIT(B))                over the bases B of C that are inside the project
DIT(C) = 1 + max(DIT(B1), DIT(B2), ...) for multiple inheritance → the longest path
```

- A class whose bases are all external/unresolved has `DIT = 0` (it is a project-local root).
- With multiple inheritance, the **longest** path wins.
- The engine also records the resolved `bases` and the full `inheritance_path` per class so the value is explainable.

## 4. Implementation Basis: Manual (no library)

DIT is **fully hand-implemented** on the Python standard library `ast` module — no Radon, no networkx.

- Engine file: `backend/analysis/engines/dit.py`
- Imports: `ast` only (`dit.py:1`) plus `pathlib`.
- Class map: `class_map` (class name → list of resolvable project-local bases) is built across all analyzed files (`dit.py:100-143`).
- Depth computation: a memoized recursive DFS, `_calculate_class_dit` (`dit.py:205-303`), following the recurrence documented at `dit.py:213-221` and implemented at `dit.py:255-298`.
- Base-name resolution: `Name → id`, `Attribute → attr` (`dit.py:306-323`).

## 5. Calculation Steps in CodeInsight

1. Collect every `ast.ClassDef` across all files; resolve each class's bases to names (`dit.py:100-143`).
2. For each class, compute `DIT(C)` recursively (`dit.py:255-298`):
   - base not in `class_map` (external or unresolvable) → candidate depth 0, chain terminates (`dit.py:262-268`);
   - multiple bases → take the maximum of their depths (`dit.py:287-289`);
   - inheritance cycles (a class appearing as its own ancestor) are protected by a visiting set → depth 0 for the cycle member (`dit.py:233-235`).

The scalar `calculate()` result is the **sum of all class DIT values** in the input (`dit.py:23-37`). Detailed output (`calculate_detailed`, `dit.py:79-97`) is grouped `files → classes[{name, dit, bases, inheritance_path, lineno, endline}]` plus `total`, `average`, `max`, `class_count`, `scope` and `completeness`.

## 6. Scope and Completeness (ADR-0001)

DIT is a project-local metric: the depth is measured over the inheritance tree of the **analyzed input** only.

- `scope = "project"` → `completeness: "full"` — the class map covers every file of the input (`dit.py:87-91`).
- `scope = "single_file"` → `completeness: "partial"` — a base defined in a file outside the input cannot be seen, so a class that inherits externally appears shallower than it truly is; the reported value is a **lower bound** (comment at `dit.py:82-86`, per ADR-0001).

## 7. Limitations

- **Project-local depth, not absolute depth.** A Django model extending `models.Model` reports DIT 0 (or its project-local depth), not its true depth including the framework hierarchy. This matches the project-local principle of the other design metrics but differs from tools that resolve the full type hierarchy.
- **Name-based base resolution.** Bases are matched by name against the project class map; aliasing or same-name classes in different modules are resolved approximately.
- **DIT measures depth, not quality.** A deep hierarchy can be legitimate; the metric is a signal to look, not a verdict.

## 8. Unit Tests

`backend/analysis/test/test_dit.py` asserts hand-computed values (ADR-0002):

- class with no project-local parent → DIT 0, path `["User"]` (`:29`)
- one level of inheritance → 1 (`:55`)
- chain A→B→C→D → DITs 0/1/2/3 (`:88`)
- multiple inheritance → longest path wins (D→B→A, DIT 2) (`:141`)
- external parent terminates the chain; bases still recorded (`:180`)
- independent trees are computed separately (`:208`)
- project aggregation: total 3, average 1.0, max 2 (`:264`)
- `scope`/`completeness`: `partial` on single_file (`:304`), `full` on project (`:329`)

## 9. References

- Chidamber, S. R. & Kemerer, C. F., *A Metrics Suite for Object Oriented Design*, IEEE TSE 20(6), 1994.
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight ADR-0002, standalone analyzer: [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- Engine: `backend/analysis/engines/dit.py` · Tests: `backend/analysis/test/test_dit.py`
- Registration: `MetricDefinition` key `DIT`, display name "Depth of Inheritance Tree", category "Design Quality" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:94-102`)
