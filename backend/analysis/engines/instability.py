from pathlib import Path

from analysis.dependency_graph import ModuleDependencyGraph

from .base import BaseMetricEngine


class InstabilityEngine(BaseMetricEngine):
    """
    Instability (Robert C. Martin): I = Ce / (Ca + Ce).

    Computed at file level over internal imports only, using the
    shared module dependency graph. `Ce` is the number of internal
    modules a file imports; `Ca` is the number of internal modules
    that import it. When `Ca + Ce = 0`, `I = 0`.

    Scope/completeness (ADR-0001): the service passes the Input
    `scope` explicitly. On `project` scope the full graph is
    reported with `completeness: full`; on `single_file` scope
    only the visible `Ce` is reported with
    `completeness: partial` — `Ca` and `I` are never claimed, so
    no value is fabricated for modules outside the Input.
    """

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> float | None:
        """
        Return the project average Instability, or None when the
        scope is `single_file` (no claimable scalar value).
        """
        result = self.calculate_detailed(
            python_files,
            scope,
        )

        return result.get("average")

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:
        graph = ModuleDependencyGraph(python_files)

        if scope == "single_file":
            return self._partial_result(
                python_files,
                graph,
            )

        return self._full_result(
            python_files,
            graph,
        )

    # ---- Full project result ----

    def _full_result(
            self,
            python_files: list[Path],
            graph: ModuleDependencyGraph,
    ) -> dict:

        files = []
        ce_total = 0
        ca_total = 0

        for file_path in python_files:
            module = graph.module_name(file_path)

            if module is None:
                continue

            imported = graph.imports(file_path)
            dependents = graph.dependents(module)

            ce = len(imported)
            ca = len(dependents)

            ce_total += ce
            ca_total += ca

            files.append(
                {
                    "file": str(file_path),
                    "module": module,
                    "ce": ce,
                    "ca": ca,
                    "i": (
                        ce / (ce + ca)
                        if ce + ca > 0
                        else 0.0
                    ),
                    "imported_modules": sorted(imported),
                    "dependent_modules": sorted(dependents),
                }
            )

        average = (
            sum(item["i"] for item in files) / len(files)
            if files
            else 0.0
        )

        return {
            "metric": "INSTABILITY",
            "scope": "project",
            "completeness": "full",
            "totals": {
                "modules": len(files),
                "ce": ce_total,
                "ca": ca_total,
            },
            "average": average,
            "files": files,
        }

    # ---- Single-file partial result ----

    def _partial_result(
            self,
            python_files: list[Path],
            graph: ModuleDependencyGraph,
    ) -> dict:

        files = []

        for file_path in python_files:
            module = graph.module_name(file_path)

            if module is None:
                continue

            imported = graph.imports(file_path)

            files.append(
                {
                    "file": str(file_path),
                    "module": module,
                    "ce": len(imported),
                    "imported_modules": sorted(imported),
                }
            )

        return {
            "metric": "INSTABILITY",
            "scope": "single_file",
            "completeness": "partial",
            "reason": (
                "Ca (incoming dependents) cannot be observed for a "
                "single-file input — only the visible Ce is "
                "reported; I is not claimed."
            ),
            "files": files,
        }
