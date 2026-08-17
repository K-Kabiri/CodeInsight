import ast
from pathlib import Path

from .base import BaseMetricEngine


class DITEngine(BaseMetricEngine):
    """
    Depth of Inheritance Tree (DIT).

    DIT of a class is the maximum length of an inheritance
    path from that class to the root of the inheritance tree.

    For multiple inheritance, the longest inheritance path
    is used.

    Only classes that can be resolved within the analyzed
    source files contribute to the inheritance depth.
    External or unresolved base classes terminate the
    project-local inheritance chain.
    """

    def calculate(self, python_files: list[Path]) -> int:
        """
        Calculate the total DIT across all classes.
        """

        result = self.calculate_detailed(python_files)

        return result["total"]

    def calculate_detailed(
            self,
            python_files: list[Path],
    ) -> dict:

        class_map = self._collect_classes(
            python_files
        )

        files = []
        all_depths = []

        for file_path in python_files:
            result = self._analyze_file(
                file_path,
                class_map,
            )

            files.append(result)

            all_depths.extend(
                item["dit"]
                for item in result["classes"]
            )

        total = sum(all_depths)

        average = (
            total / len(all_depths)
            if all_depths
            else 0.0
        )

        maximum = (
            max(all_depths)
            if all_depths
            else 0
        )

        return {
            "metric": "DIT",
            "total": total,
            "average": average,
            "max": maximum,
            "class_count": len(all_depths),
            "files": files,
        }

    # Collect classes
    @staticmethod
    def _collect_classes(
            python_files: list[Path],
    ) -> dict:

        class_map = {}

        for file_path in python_files:

            source_code = file_path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source_code,
                filename=str(file_path),
            )

            for node in ast.walk(tree):

                if not isinstance(
                        node,
                        ast.ClassDef,
                ):
                    continue

                class_name = node.name

                bases = []

                for base in node.bases:

                    base_name = (
                        DITEngine._resolve_base_name(
                            base
                        )
                    )

                    if base_name is not None:
                        bases.append(base_name)

                class_map[class_name] = bases

        return class_map

    # File analysis
    @staticmethod
    def _analyze_file(
            file_path: Path,
            class_map: dict,
    ) -> dict:

        source_code = file_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source_code,
            filename=str(file_path),
        )

        classes = []

        for node in ast.walk(tree):

            if not isinstance(
                    node,
                    ast.ClassDef,
            ):
                continue

            dit, path = (
                DITEngine._calculate_class_dit(
                    node.name,
                    class_map,
                )
            )

            classes.append(
                {
                    "name": node.name,
                    "dit": dit,
                    "bases": class_map.get(
                        node.name,
                        [],
                    ),
                    "inheritance_path": path,
                    "lineno": node.lineno,
                    "endline": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                }
            )

        return {
            "file": str(file_path),
            "total": sum(
                item["dit"]
                for item in classes
            ),
            "classes": classes,
        }

    # DIT calculation
    @staticmethod
    def _calculate_class_dit(
            class_name: str,
            class_map: dict,
    ) -> tuple[int, list[str]]:
        """
        Calculate DIT using the longest inheritance path.

        DIT(C) = 0
            if C has no resolvable project-local parent.

        Otherwise:

            DIT(C) =
                1 + max(DIT(parent))
        """

        cache = {}

        def calculate(
                current_class: str,
                visiting: set[str],
        ) -> tuple[int, list[str]]:

            if current_class in cache:
                return cache[current_class]

            # Protect against invalid/cyclic inheritance.
            if current_class in visiting:
                return 0, [current_class]

            visiting = visiting | {current_class}

            bases = class_map.get(
                current_class,
                [],
            )

            # No project-local parent.
            if not bases:
                result = (
                    0,
                    [current_class],
                )

                cache[current_class] = result

                return result

            best_depth = 0
            best_path = [
                current_class
            ]

            for base in bases:

                if base not in class_map:
                    # External/unresolved parent.
                    candidate_depth = 0
                    candidate_path = [
                        current_class,
                        base,
                    ]

                else:
                    parent_depth, parent_path = (
                        calculate(
                            base,
                            visiting,
                        )
                    )

                    candidate_depth = (
                            parent_depth + 1
                    )

                    candidate_path = [
                        current_class,
                        *parent_path,
                    ]

                if candidate_depth > best_depth:
                    best_depth = candidate_depth
                    best_path = candidate_path

            result = (
                best_depth,
                best_path,
            )

            cache[current_class] = result

            return result

        return calculate(
            class_name,
            set(),
        )

    # Base name resolution
    @staticmethod
    def _resolve_base_name(
            node: ast.expr,
    ) -> str | None:

        if isinstance(
                node,
                ast.Name,
        ):
            return node.id

        if isinstance(
                node,
                ast.Attribute,
        ):
            return node.attr

        return None
