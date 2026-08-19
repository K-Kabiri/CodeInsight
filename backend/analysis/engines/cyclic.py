from pathlib import Path

from analysis.dependency_graph import ModuleDependencyGraph

from .base import BaseMetricEngine


class CyclicDependenciesEngine(BaseMetricEngine):
    """
    Cyclic Dependencies: cycles in the module dependency graph.

    A cycle is a strongly connected component (SCC) with at least
    two member modules; each SCC is reported once with its member
    modules. A self-loop (a module importing itself) is handled
    separately in `self_loops` and never reported as a spurious
    cycle.

    Scope/completeness (ADR-0001): on `single_file` scope the
    metric reports `completeness: not_applicable` — cycles cannot
    exist within a single module, and no number is fabricated. On
    `project` scope the full graph is analyzed with
    `completeness: full`.
    """

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> int | None:
        """
        Return the number of dependency cycles, or None when the
        scope is `single_file` (not applicable).
        """
        result = self.calculate_detailed(
            python_files,
            scope,
        )

        if result["completeness"] == "not_applicable":
            return None

        return len(result["cycles"])

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:

        if scope == "single_file":
            return {
                "metric": "CYCLIC",
                "scope": "single_file",
                "completeness": "not_applicable",
                "reason": (
                    "Dependency cycles require at least two modules — "
                    "not applicable to a single-file input."
                ),
                "cycles": [],
                "self_loops": [],
            }

        graph = ModuleDependencyGraph(python_files)

        cycles, self_loops = self._find_cycles(graph)

        return {
            "metric": "CYCLIC",
            "scope": "project",
            "completeness": "full",
            "cycles": cycles,
            "self_loops": self_loops,
        }

    @staticmethod
    def _find_cycles(
            graph: ModuleDependencyGraph,
    ) -> tuple[list[list[str]], list[str]]:

        adjacency = {
            module: graph.out_edges(module)
            for module in graph.modules()
        }

        self_loops = sorted(
            module
            for module, targets in adjacency.items()
            if module in targets
        )

        components = _strongly_connected_components(adjacency)

        cycles = sorted(
            (
                sorted(component)
                for component in components
                if len(component) >= 2
            ),
            key=lambda cycle: (len(cycle), cycle),
        )

        return cycles, self_loops


def _strongly_connected_components(
        adjacency: dict[str, set[str]],
) -> list[list[str]]:
    """
    Tarjan's strongly connected components algorithm over a
    module-name adjacency map. An SCC of two or more modules is a
    dependency cycle; a single-node SCC with no self-edge is not.
    """
    index = {}
    lowlink = {}
    stack = []
    on_stack = set()
    counter = 0
    components = []

    def visit(node: str) -> None:
        nonlocal counter

        index[node] = counter
        lowlink[node] = counter
        counter += 1

        stack.append(node)
        on_stack.add(node)

        for successor in adjacency.get(node, ()):
            if successor not in index:
                visit(successor)
                lowlink[node] = min(
                    lowlink[node],
                    lowlink[successor],
                )
            elif successor in on_stack:
                lowlink[node] = min(
                    lowlink[node],
                    index[successor],
                )

        if lowlink[node] == index[node]:
            component = []

            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)

                if member == node:
                    break

            components.append(component)

    for node in adjacency:
        if node not in index:
            visit(node)

    return components
