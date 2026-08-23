# Instability (I)

## 1. Overview

**Instability (I)** is a dependency-structure metric introduced by Robert C. Martin. It measures a module's tendency to change with its dependents: a module that many other modules depend on is hard to change (a change ripples to all dependents — it is *stable*), while a module that itself depends on many others is likely to be forced to change when they change (it is *unstable*). Instability is the ratio of a module's outgoing dependencies to its total coupling:

```text
I = Ce / (Ca + Ce)
```

where:

- **Ce — Efferent Couplings (outgoing):** the number of other modules this module depends on (modules it imports).
- **Ca — Afferent Couplings (incoming):** the number of other modules that depend on this module (modules that import it).

In CodeInsight, Instability is computed at **file level** (one module = one `.py` file) over **internal imports only**: an edge exists only between two modules of the analyzed input; external libraries such as `django` or `requests` never count. When `Ca + Ce = 0`, the engine reports `I = 0` (Section 3.3).

Scope and completeness follow [ADR-0001](adr/0001-metric-scope-completeness-contract.md): on a `single_file` input, `Ca` is unobservable and the engine reports only the visible internal `Ce` with `completeness: partial` — it never assumes `Ca = 0` and emits a precise-looking value; on a `project` input it reports the full graph with `completeness: full`. The engine also reports a project-level average.

## 2. Purpose

Instability quantifies how much a module resists change because of its position in the dependency graph:

- A module with **many dependents** (`Ca` high) is hard to change, because a change must be re-validated against everything that depends on it.
- A module that **depends on many others** (`Ce` high) is likely to change, because it inherits the changes of everything it depends on.

The metric is one half of Martin's dependency-analysis framework: together with Abstractness (A), it defines the "main sequence" line `A + I = 1`, and the Distance (D) metric measures how far a package sits from that line. The framework is presented in Martin's package-design work (*Design Principles and Design Patterns*, 2000; *Agile Software Development*, 2002) and implemented by reference tools such as NDepend, JDepend and PHP Depend.

The design rule built on Instability is Martin's **Stable Dependencies Principle (SDP)**: *"Depend in the direction of stability."* A well-structured system arranges dependencies so that unstable (easy-to-change) modules depend on stable (hard-to-change) modules, never the reverse. In CodeInsight terms: `I = 0` marks a maximally stable module, `I = 1` a maximally unstable one.

Instability is a design-level signal, not a verdict: entry points, controllers and glue code are *expected* to be unstable. The value matters in aggregate.

## 3. Reference Definition

### 3.1 Origin

The metric family was introduced by Robert C. Martin in the 1994 whitepaper *OO Design Quality Metrics — An Analysis of Dependencies*, and presented at package granularity in *Design Principles and Design Patterns* (2000) and *Agile Software Development: Principles, Patterns, and Practices* (2002).

### 3.2 Definitions and formula

The canonical package-level definitions, as documented by JDepend's report documentation:

> **Afferent Couplings** — The number of other packages that depend upon classes within the package is an indicator of the package's responsibility.
>
> **Efferent Couplings** — The number of other packages that the classes in the package depend upon is an indicator of the package's independence.
>
> **Instability** — The ratio of efferent coupling (Ce) to total coupling (Ce / (Ce + Ca)). This metric is an indicator of the package's resilience to change. The range for this metric is 0 to 1, with I=0 indicating a completely stable package and I=1 indicating a completely instable package.

So, in CodeInsight terms:

```text
I = Ce / (Ca + Ce)          range [0, 1]
Ce = outgoing edges         modules this file imports
Ca = incoming edges         files that import this file
```

Note the "outside this package" boundary in the definitions: `Ca` counts *other* packages that depend on the package, and `Ce` counts *other* packages that the package depends upon. CodeInsight mirrors this boundary at file level with its internal-imports-only rule (Section 5).

### 3.3 The 0/0 case

At `Ca = 0` and `Ce = 0` the formula is the undefined ratio `0/0`. The literature's reading of the metric supplies the convention: `I = 0` denotes a package that "depends upon nothing" or is "completely stable", which is exactly the no-dependency case. Reference implementations therefore report `I = 0` when there is nothing to couple, and CodeInsight follows the same convention — `I = 0` with no division error (`instability.py:92-96`). This is a documented convention, not a mathematical derivation.

## 4. Implementation Basis: Manual (no library)

Instability is **fully hand-implemented** on top of CodeInsight's shared, hand-rolled module dependency graph. There is **no library**: no networkx, no Radon coupling metrics.

- Engine file: `backend/analysis/engines/instability.py`
- Shared graph: `backend/analysis/dependency_graph.py` — `ModuleDependencyGraph`, built by parsing `ast.Import`/`ast.ImportFrom` nodes (see Section 5).
- Formula implementation: `instability.py:80-96`; the `Ca + Ce = 0 → I = 0` guard at `instability.py:92-96`.
- Graph lookups: `graph.imports(file)` gives the Ce targets (`instability.py:77`), `graph.dependents(module)` gives the Ca set (`instability.py:78`), `graph.module_name` names the node (`instability.py:72`).

Radon — the library CodeInsight already uses for LOC/complexity — has **no** Instability or coupling metrics of any kind; it is a per-file, dependency-free metrics library. SonarQube likewise does not offer Martin's Instability for Python (its old Java-only afferent/efferent couplings were removed in the 4.x era). So no reference Python library exists, and a custom engine on the shared graph is required.

## 5. Calculation Steps in CodeInsight

**Granularity.** File level: one module is one `.py` file. (Martin's canonical definitions are package-level; this is a documented granularity divergence.)

**Shared dependency graph.** `ModuleDependencyGraph` (`backend/analysis/dependency_graph.py`) is built once per analysis:

- Nodes = modules of the input; a dotted module name is the path relative to the input root (`pkg/mod.py → pkg.mod`) (`_build`, `dependency_graph.py:79-135`).
- Edges are parsed from `ast.Import` / `ast.ImportFrom` per file: `import a.b`, `from a import b`, `from a.b import c`, and relative imports (`_resolve_imports`, `dependency_graph.py:139-178`).
- Resolution: the **longest internal prefix** of a dotted name present in the module map creates the edge; imports resolving outside the input — `django`, `requests`, the standard library — never create edges (`_resolve_absolute`, `dependency_graph.py:180-193`; `_resolve_from_import`, `:195-211`; `_resolve_relative`, `:213-240`).
- Edge direction: **importer → imported**; `out_edges` are the modules a file imports, `dependents` is the reverse index (`dependency_graph.py:53-69`).

**Per-module Instability** (`instability.py:80-96`):

```text
ce = |graph.imports(file)|      internal modules this file imports
ca = |graph.dependents(module)| internal modules that import it
I  = ce / (ca + ce), or 0.0 when ca + ce = 0
```

**Aggregation.** The scalar `calculate()` returns the **project average** of per-module `I` (`instability.py:25-39`). Detailed output (`instability.py:86-119`): per module `{file, module, ce, ca, i, imported_modules, dependent_modules}`, plus `totals {modules, ce, ca}`, `average`, `scope: "project"`, `completeness: "full"`.

## 6. Scope and Completeness (ADR-0001)

The engine receives the input `scope` (`single_file` / `project`) explicitly from the service — never inferred from file count, so a one-file ZIP is still a `project`.

- `scope = "project"` → `Ca` and `Ce` over the full module graph, `completeness: "full"`.
- `scope = "single_file"` → `Ca` is unobservable by definition; the engine reports `_partial_result` (`instability.py:123-157`): only the visible internal `ce` and `imported_modules` per file, `completeness: "partial"`, an explicit `reason` ("Ca … cannot be observed for a single-file input — only the visible Ce is reported; I is not claimed"), **no** per-file `ca`/`i`, no `average`/`totals`, and `calculate()` returns `None` (`instability.py:39`, tested at `test_instability.py:306-311`). The engine never assumes `Ca = 0` to emit a precise-looking value — that option was explicitly rejected in ADR-0001.

## 7. Limitations

- **Granularity: package → file.** Martin's definitions and all reference tools (NDepend, JDepend, PHP Depend) operate on packages; CodeInsight computes at file level. Values are not directly comparable to package-level tools.
- **Dependency resolution and edge counting vs NDepend.** NDepend resolves dependencies from a compiled code model over assemblies/types/namespaces; CodeInsight parses import statements over files. Edge sets differ in principle, so `Ca`/`Ce` counts are not expected to match exactly even on equivalent code.
- **No Python reference tool exists.** Neither Radon nor SonarQube computes Instability or afferent/efferent couplings for Python. Cross-validation is therefore limited to documented comparison — never a test or runtime dependency (ADR-0002).
- **External libraries excluded.** Only internal imports create edges; external-library dependents never contribute to `Ca`/`Ce`.
- **0/0 convention.** `I = 0` for `Ca + Ce = 0` is a documented convention (Section 3.3).

## 8. Unit Tests

`backend/analysis/test/test_instability.py` asserts hand-computed values (ADR-0002 — no reference tool is ever invoked):

- hand-computed stable/unstable project: `core` I=0.2 (ca=4, ce=1), `app` I=1.0, `x` I=0.0; totals ce=5, ca=5; average computed from the fixtures (`:42`)
- import forms and internal-only edges: absolute, `from`, `from … import sub`, relative; external/stdlib names never edges or modules (`:120`)
- longest-internal-prefix fallback (`import pkg.external` → edge to `pkg`) (`:206`)
- 0/0 case → 0.0, no division error (`:233`)
- single_file → partial, no `ca`/`i`/`average`, `calculate()` → None (`:267`)
- engine registered in `ENGINE_REGISTRY` (`:314`) and `MetricDefinition` seeded (`:328`)

## 9. References

- Robert C. Martin, *OO Design Quality Metrics — An Analysis of Dependencies*, 1994 — [PDF (DePaul-hosted copy)](https://condor.depaul.edu/~dmumaugh/OOT/Design-Principles/oodmetrc.pdf)
- Robert C. Martin, *Design Principles and Design Patterns*, 2000
- Robert C. Martin, *Agile Software Development: Principles, Patterns, and Practices*, Prentice Hall, 2002, ISBN 978-0-13-597444-5
- JDepend (Java) — package-level Ca, Ce, I, A, D: [github.com/clarkware/jdepend](https://github.com/clarkware/jdepend); report documentation mirror: [svn.apache.org](https://svn.apache.org/repos/asf/james/server/tags/2_3_2RC1/tools/etc/jdepend.xsl)
- PHP Depend — Abstraction Instability Chart and metric definitions: [pdepend.org](http://pdepend.org/documentation/handbook/reports/abstraction-instability-chart.html)
- NDepend API — `IAssembly.Instability`: [ndepend.com/api](https://www.ndepend.com/api/NDepend.API~NDepend.CodeModel.IAssembly~Instability.html)
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight ADR-0002, standalone analyzer: [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- Engine: `backend/analysis/engines/instability.py` · Shared graph: `backend/analysis/dependency_graph.py` · Tests: `backend/analysis/test/test_instability.py`
- Registration: `MetricDefinition` key `INSTABILITY`, display name "Instability", category "Design Quality" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:108-117`)
