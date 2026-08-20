"""
Reusable module dependency graph for dependency-based metrics.

Nodes are the Python modules of an analyzed Input; an edge exists
when one module imports another module that is itself part of the
Input — the same project-local principle the CBO engine applies to
classes. External libraries, the standard library and unresolvable
names never create edges.

Module naming: a module's dotted name is its path relative to the
common ancestor directory of all analyzed files. `pkg/mod.py` is
`pkg.mod`; `pkg/__init__.py` is the package `pkg`; a root-level
`__init__.py` has no importable name and is not a node.

Import forms covered: `import a.b`, `from a import b`,
`from a.b import c`, and relative imports resolved within the
project tree. For `import a.b` where `a.b` is not part of the Input
but `a` is, the edge falls back to the longest internal prefix `a`.
Files that fail to parse contribute no out-edges but remain nodes.
"""

import ast
import os
from collections import defaultdict
from pathlib import Path


class ModuleDependencyGraph:

    def __init__(self, python_files: list[Path]):
        self._module_map: dict[str, Path] = {}
        self._file_to_module: dict[Path, str] = {}
        self._imports: dict[Path, set[str]] = {}
        self._dependents: dict[str, set[str]] = defaultdict(set)

        self._build(python_files)

    # ---- Public API ----

    def module_name(self, file_path: Path) -> str | None:
        """
        The dotted module name of a file, or None if the file is
        not a node in the graph (e.g. a root-level `__init__.py`).
        """
        return self._file_to_module.get(file_path)

    def imports(self, file_path: Path) -> set[str]:
        """
        The internal modules (dotted names) that a file imports.
        """
        return set(self._imports.get(file_path, ()))

    def out_edges(self, module_name: str) -> set[str]:
        """
        The internal modules (dotted names) that a module imports,
        addressed by module name.
        """
        file_path = self._module_map.get(module_name)

        if file_path is None:
            return set()

        return set(self._imports.get(file_path, ()))

    def dependents(self, module_name: str) -> set[str]:
        """
        The internal modules (dotted names) that import a module.
        """
        return set(self._dependents.get(module_name, ()))

    def modules(self) -> set[str]:
        """
        All module names in the graph.
        """
        return set(self._module_map.keys())

    # ---- Construction ----

    def _build(self, python_files: list[Path]) -> None:
        root = self._common_ancestor(python_files)

        for file_path in python_files:
            name = self._module_name(file_path, root)

            if name is None:
                continue

            self._module_map[name] = file_path
            self._file_to_module[file_path] = name

        for file_path in python_files:
            importer = self._file_to_module.get(file_path)

            if importer is None:
                continue

            targets = self._resolve_imports(file_path)

            self._imports[file_path] = targets

            for target in targets:
                self._dependents[target].add(importer)

    @staticmethod
    def _common_ancestor(
            python_files: list[Path],
    ) -> Path:
        parents = [file_path.parent for file_path in python_files]

        if not parents:
            return Path.cwd()

        if len(parents) == 1:
            return parents[0]

        return Path(
            os.path.commonpath(
                [str(parent) for parent in parents]
            )
        )

    @staticmethod
    def _module_name(
            file_path: Path,
            root: Path,
    ) -> str | None:
        rel = file_path.relative_to(root)
        parts = rel.parts

        if parts[-1] == "__init__.py":
            name = ".".join(parts[:-1])
        else:
            name = ".".join((*parts[:-1], file_path.stem))

        return name or None

    # ---- Import resolution ----

    def _resolve_imports(
            self,
            file_path: Path,
    ) -> set[str]:
        try:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8"),
                filename=str(file_path),
            )
        except (OSError, SyntaxError):
            return set()

        current_module = self._file_to_module[file_path]
        targets = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = self._resolve_absolute(alias.name)
                    if target:
                        targets.add(target)

            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    target = self._resolve_relative(
                        node,
                        current_module,
                    )
                elif node.module:
                    target = self._resolve_from_import(
                        node.module,
                        node.names,
                    )
                else:
                    target = None

                if target:
                    targets.add(target)

        return targets

    def _resolve_absolute(self, name: str) -> str | None:
        """
        Resolve a dotted name to the longest internal prefix
        that is a module of the Input.
        """
        parts = name.split(".")

        for length in range(len(parts), 0, -1):
            candidate = ".".join(parts[:length])

            if candidate in self._module_map:
                return candidate

        return None

    def _resolve_from_import(
            self,
            module: str,
            names,
    ) -> str | None:
        """
        Resolve `from module import name`: if `module.name` is
        itself an internal module the edge targets it, otherwise
        it targets `module` (the longest internal prefix).
        """
        if len(names) == 1 and names[0].name != "*":
            submodule = f"{module}.{names[0].name}"

            if submodule in self._module_map:
                return submodule

        return self._resolve_absolute(module)

    def _resolve_relative(
            self,
            node: ast.ImportFrom,
            current_module: str,
    ) -> str | None:
        """
        Resolve a relative import against the current module's
        package: `node.level` dots drop that many trailing parts
        of the current module name to find the base package.
        """
        parts = current_module.split(".")

        if node.level > len(parts):
            return None

        base_parts = parts[: len(parts) - node.level]

        if not base_parts:
            return None

        base = ".".join(base_parts)

        if node.module:
            module = f"{base}.{node.module}"
        else:
            module = base

        return self._resolve_from_import(module, node.names)
