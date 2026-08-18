from pathlib import Path

from radon.complexity import cc_rank, cc_visit

from .base import BaseMetricEngine


class CyclomaticComplexityEngine(BaseMetricEngine):

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> int:
        """
        Calculate the total Cyclomatic Complexity of all Python files.

        Radon's default Cyclomatic Complexity starts each analyzed
        block with a base complexity of 1.
        """
        result = self.calculate_detailed(
            python_files,
            scope,
        )

        return result["total"]

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict:
        """
        Calculate Cyclomatic Complexity with file-level and
        block-level details.

        Returns:
            {
                "total": int,
                "average": float,
                "files": [...]
            }
        """

        files = []
        all_complexities = []

        for file_path in python_files:
            file_result = self._analyze_file(file_path)

            files.append(file_result)

            all_complexities.extend(
                block["complexity"]
                for block in file_result["blocks"]
            )

        total = sum(all_complexities)

        average = (
            total / len(all_complexities)
            if all_complexities
            else 0.0
        )

        return {
            "total": total,
            "average": average,
            "files": files,
        }

    @staticmethod
    def _analyze_file(file_path: Path) -> dict:
        """
        Analyze a single Python file using Radon's
        Cyclomatic Complexity visitor.
        """

        source_code = file_path.read_text(
            encoding="utf-8"
        )

        blocks = cc_visit(source_code)

        block_results = []

        for block in blocks:
            block_results.append(
                CyclomaticComplexityEngine._serialize_block(
                    block
                )
            )

        return {
            "file": str(file_path),
            "total": sum(
                block["complexity"]
                for block in block_results
            ),
            "blocks": block_results,
        }

    @staticmethod
    def _serialize_block(block) -> dict:
        """
        Convert a Radon Function or Class object
        into a serializable dictionary.
        """

        result = {
            "name": block.name,
            "type": (
                "class"
                if hasattr(block, "methods")
                else (
                    "method"
                    if getattr(block, "is_method", False)
                    else "function"
                )
            ),
            "complexity": block.complexity,
            "rank": cc_rank(block.complexity),
            "lineno": block.lineno,
            "endline": block.endline,
            "col_offset": block.col_offset,
        }

        if hasattr(block, "classname"):
            result["classname"] = block.classname

        if hasattr(block, "is_method"):
            result["is_method"] = block.is_method

        if hasattr(block, "real_complexity"):
            result["real_complexity"] = block.real_complexity

        if hasattr(block, "methods"):
            result["methods"] = [
                CyclomaticComplexityEngine._serialize_block(
                    method
                )
                for method in block.methods
            ]

        return result