# Cyclic Dependencies

## 1. Overview

**Cyclic Dependencies** is a dependency-structure metric that reports cycles in the module dependency graph of the analyzed input. A cycle exists when a set of modules import each other in a loop (`a → b → a`, or longer rings) — a structure that makes the modules impossible to build, test or reason about in isolation, and a classic sign of a design problem (the Dependency Inversion / Stable Dependencies principles are violated somewhere).

In CodeInsight, a cycle is defined as a **strongly connected component (SCC) with at least two member modules** in the shared module dependency graph, computed with a **hand-implemented Tarjan SCC algorithm**. Self-loops (a module importing itself) are detected separately and are never reported as cycles.

## 2. Purpose

Cyclic dependencies are a maintainability risk: when modules form a ring, none of them can be understood or changed independently, and the coupling surface grows combinatorially. The metric surfaces these rings so they can be broken (typically by extracting the shared dependency). It is reported alongside Instability, which quantifies each module's position in the same dependency graph.

## 3. Reference Definition

The metric is graph-theoretic: on a directed graph where nodes are modules and edges are import relationships (importer → imported), a **cycle** is a strongly connected component with more than one node — every member can reach every other member. This is the standard SCC definition (Tarjan 1972). CodeInsight applies it to the **project-internal** module graph: external libraries and the standard library never participate, mirroring the project-local principle of Instability and CBO.

The engine's docstring (`cyclic.py:8-23`) pins the definition: a cycle = SCC with ≥ 2 members, each reported once with sorted members; a self-loop is separated into `self_loops` and never reported as a spurious cycle.

## 4. Implementation Basis: Manual (no library)

Cyclic Dependencies is **fully hand-implemented** on top of CodeInsight's shared, hand-rolled `ModuleDependencyGraph`. There is **no library**: no networkx, no Radon.

- Engine file: `backend/analysis/engines/cyclic.py`
- Shared graph: `backend/analysis/dependency_graph.py` — `ModuleDependencyGraph` (nodes = modules of the input, edges = import direction; see Section 5)
- Cycle detection: a **hand-implemented classic Tarjan SCC** — `_strongly_connected_components` (`cyclic.py:105-160`), using index/lowlink/stack/on_stack (`cyclic.py:113-158`)
- Cycle extraction: `_find_cycles` (`cyclic.py:75-102`) builds adjacency from `graph.out_edges`, detects self-loops (`cyclic.py:85-89`), and filters SCCs by `len(component) >= 2` (`cyclic.py:93-100`)

## 5. Calculation Steps in CodeInsight

1. Build the shared `ModuleDependencyGraph` over the analyzed input (see [Instability.md](Instability.md) Section 5 for the graph construction): nodes are dotted module names, edges point importer → imported, and only project-internal imports create edges.
2. Build the adjacency map from `graph.out_edges` (`cyclic.py:80-83`).
3. Separate **self-loops** (module importing itself) into `self_loops` (`cyclic.py:85-89`).
4. Run the Tarjan SCC algorithm over the remaining graph (`cyclic.py:105-160`).
5. Report each SCC with `len >= 2` as one cycle, members sorted (`cyclic.py:93-100`).
6. Scalar `calculate()` returns `len(result["cycles"])` — the number of cycles — or `None` when not applicable (`cyclic.py:25-42`).
7. Detailed output (`cyclic.py:67-73`): `{metric, scope, completeness, cycles: [["a", "b"], ...], self_loops: ["x"]}` — the count is the scalar; the detail carries the actual cycle members.

## 6. Scope and Completeness (ADR-0001)

- `scope = "project"` → `completeness: "full"` — the SCC analysis runs over the full module graph (`cyclic.py:67-73`).
- `scope = "single_file"` → `completeness: "not_applicable"` with a human-readable reason ("Dependency cycles require at least two modules…"), empty `cycles`/`self_loops`, and `calculate()` returns `None` (`cyclic.py:39-40, 50-61`) — a single file cannot form a cycle, so no value is fabricated (ADR-0001).

## 7. Limitations

- **Project-internal only.** Cycles through external libraries are invisible (the graph never contains them), so a cycle that only closes through an external package is not reported. This is the same boundary as Instability and CBO.
- **Import-level resolution.** Edges come from `ast.Import`/`ast.ImportFrom` resolution, not from actual runtime imports — dynamic imports (`importlib.import_module`) create no edges.
- **Count, not severity.** The scalar counts cycles; the detail's member lists show *which* modules form each ring, and severity is left to the reader (a 2-module ring vs. a 10-module ring).

## 8. Unit Tests

`backend/analysis/test/test_cyclic.py`:

- two-module cycle reported once, `calculate()` → 1 (`:39`)
- three-module cycle with non-cyclic tail `d` excluded (`:77`)
- disjoint cycles each reported once → 2 (`:102`)
- self-loop `x` goes to `self_loops`, not a cycle → 0 (`:131`)
- acyclic graph → 0 (`:162`)
- single_file → `not_applicable`, `calculate()` → None (`:188`)
- engine registered in `ENGINE_REGISTRY` (`:221`) and `MetricDefinition` seeded (`:235`)

## 9. References

- Robert Tarjan, *Depth-First Search and Linear Graph Algorithms*, SIAM Journal on Computing, 1(2), 1972 (the SCC algorithm).
- Robert C. Martin's package-design principles (Acyclic Dependencies Principle — no cycles in the dependency graph): *Agile Software Development*, Prentice Hall, 2002.
- CodeInsight ADR-0001, scope/completeness contract: [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md)
- CodeInsight ADR-0002, standalone analyzer: [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md)
- Engine: `backend/analysis/engines/cyclic.py` · Shared graph: `backend/analysis/dependency_graph.py` · Tests: `backend/analysis/test/test_cyclic.py`
- Registration: `MetricDefinition` key `CYCLIC`, display name "Cyclic Dependencies", category "Design Quality" (`backend/analysis/migrations/0005_seed_canonical_catalog.py:123-132`)
