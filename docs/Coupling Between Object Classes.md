# Coupling Between Object Classes (CBO)

## 1. Overview

**Coupling Between Object Classes (CBO)** is a design-quality metric introduced by Chidamber and Kemerer in their 1994 object-oriented metrics suite. It counts how many other classes a given class is coupled to: a class is coupled to another class when it uses that class in any way — through inheritance, instantiation, annotations, method calls or attribute access.

In CodeInsight, CBO is computed at **class level** for every class defined in the analyzed Python files, and the engine also reports a project total, average and per-class detail. Only couplings to classes defined **inside the analyzed input** are counted — external or standard-library classes are invisible to the metric (the project-local principle, shared with Instability and Cyclic Dependencies).

## 2. Reference Definition

The metric comes from Chidamber and Kemerer, *"A Metrics Suite for Object Oriented Design"*, IEEE Transactions on Software Engineering, 20(6), 1994:

> CBO for a class is a count of the number of other classes to which it is coupled. Coupling is measured by counting the number of distinct non-inheritance related classes on which the class depends … A class is coupled to another class if the methods of one use the methods or instance variables of the other.

The intuition behind the metric: excessive coupling makes a class hard to reuse and hard to change in isolation — a change in one class ripples into every class coupled to it. The CodeInsight engine implements the C&K definition **with the inheritance coupling included** (a base class is a coupling target too), which is the common operational variant; each coupling source is documented in Section 5.

## 3. Formula

Per class:

```text
CBO(C) = | { D : D is a class defined in the analyzed project and C is coupled to D } |
```

where "coupled to D" means the class body of C **references** D in any of the coupling positions listed in Section 5. The set semantics matter:

- **Distinct classes count once** — multiple references to the same class contribute a single coupling (`cbo.py:157-170`).
- **Self-reference is excluded** — a class is never coupled to itself (`cbo.py:163`).

The engine's scalar `calculate()` result is the **sum of all class CBOs** in the input (`cbo.py:26-31`); the detailed output carries the per-class values, the total, the average and the class count.

## 4. Implementation Basis: Manual (no library)

CBO is **fully hand-implemented** on the Python standard library `ast` module. There is **no library** involved: no Radon, no networkx, no external coupling analyzer.

- Engine file: `backend/analysis/engines/cbo.py`
- Imports: `ast` only (`cbo.py:1`) — plus `pathlib` for the file list.
- Class discovery: `ast.walk` over `ast.ClassDef` nodes of every analyzed file (`cbo.py:102-111`).
- Coupling collection: a custom `_CBOVisitor(ast.NodeVisitor)` walks each class body (`cbo.py:173-363`).
- Project class index: a `set[str]` of every class name defined across all analyzed files, used to decide whether a referenced name is an in-project class (`_add_if_class`, `cbo.py:338-346`).

The definition used is the name-based C&K definition: references are resolved **by name** against the project class index, not by full type resolution. This is a documented approximation (Section 7).

## 5. Calculation Steps in CodeInsight

For each class, the visitor collects references from these coupling sources (all in `cbo.py`):

| Coupling source | AST nodes | Code reference |
|---|---|---|
| Inheritance bases | `ClassDef.bases` | `cbo.py:209-210` |
| Decorators | `ClassDef.decorator_list` | `cbo.py:213-214` |
| Parameter / return annotations | `FunctionDef` annotations | `cbo.py:241-265` |
| Object creation | `Call` (instantiation) | `cbo.py:275-289` |
| Attribute access | `Attribute` | `cbo.py:292-306` |
| Annotated assignments | `AnnAssign` | `cbo.py:309-316` |
| Bare name references | `Name` | `cbo.py:319-324` |

Name extraction from a reference: `Name → id`, `Attribute → attr`, `Subscript → recurse into the subscript` (`cbo.py:349-363`). Every candidate name is passed to `_add_if_class`, which only adds it to `coupled_classes` when the name is in the project class index; non-class names (functions, variables, external names) are ignored.

The per-class value is `cbo = len(coupled_classes)` (`cbo.py:169-170`). Detailed output (`calculate_detailed`, `cbo.py:67-84`) is grouped `files → classes[{name, cbo, coupled_classes, lineno, endline}]` plus `total`, `average`, `class_count`, `scope` and `completeness`.

## 6. Scope and Completeness (ADR-0001)

CBO is a project-local, dependency-based metric: the class index is built from the analyzed input, and a coupling only exists to a class **inside** that input.

- `scope = "project"` → `completeness: "full"` — the class index covers every file of the input (`cbo.py:75-79`).
- `scope = "single_file"` → `completeness: "partial"` — only couplings to classes in that one file are observable; the reported value is a **lower bound** on the true coupling, and the engine never assumes the unobservable couplings are zero (ADR-0001).

## 7. Limitations

- **Name-based resolution.** Couplings are resolved by name against the project class index, not by full type/import resolution. Two classes with the same name in different modules are treated as one index entry, and a class referenced through an alias resolves by the alias's final attribute name. This is an approximation of C&K's definition, which assumes full type knowledge.
- **Project-local only.** Couplings to external or standard-library classes are never counted — matching the project-local principle of the dependency-based metrics, but diverging from tools that count external coupling when configured to.
- **Single-file lower bound.** On a single-file input the value is a lower bound (Section 6).

## 8. Unit Tests

`backend/analysis/test/test_cbo.py` asserts hand-computed values, never invoking a reference tool (ADR-0002):

- zero coupling → 0 (`:28`)
- instantiation creates one coupling → 1 (`:48`)
- multiple references to the same class count once → 1 (`:84`)
- multiple coupled classes → 2 (`:117`)
- inheritance base creates coupling → 1 (`:162`)
- type annotations create coupling → 1 (`:195`)
- non-class names are ignored → 0 (`:228`)
- `scope`/`completeness`: `partial` on single_file (`:253`), `full` on project (`:278`)

## 9. References

- Chidamber, S. R. & Kemerer, C. F., *A Metrics Suite for Object Oriented Design*, IEEE TSE 20(6), 1994.
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight ADR-0002, standalone analyzer: [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- Engine: `backend/analysis/engines/cbo.py` · Tests: `backend/analysis/test/test_cbo.py`
- Registration: `MetricDefinition` key `CBO`, display name "Coupling Between Object Classes", category "Design Quality" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:65-74`)
