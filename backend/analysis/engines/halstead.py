from pathlib import Path

from radon.metrics import h_visit

from .base import BaseMetricEngine


class HalsteadEngine(BaseMetricEngine):

    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> float:
        """
        Calculate the total Halstead Volume across all Python files.

        Halstead metrics are calculated using Radon's
        Halstead analysis implementation.
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
        Calculate Halstead metrics for all Python files.

        The main metric returned by this engine is Halstead Volume.

        Returns:
            {
                "total": float,
                "average": float,
                "files": [...]
            }
        """

        files = []
        all_volumes = []

        for file_path in python_files:
            file_result = self._analyze_file(file_path)

            files.append(file_result)
            all_volumes.append(file_result["volume"])

        total = sum(all_volumes)

        average = (
            total / len(all_volumes)
            if all_volumes
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
        Halstead visitor.
        """

        source_code = file_path.read_text(
            encoding="utf-8"
        )

        result = h_visit(source_code)
        total = result.total

        vocabulary = total.h1 + total.h2
        length = total.N1 + total.N2

        return {
            "file": str(file_path),

            "volume": total.volume,

            "vocabulary": vocabulary,
            "length": length,

            "distinct_operators": total.h1,
            "distinct_operands": total.h2,

            "total_operators": total.N1,
            "total_operands": total.N2,

            "calculated_length": total.calculated_length,
            "difficulty": total.difficulty,
            "effort": total.effort,
            "time": total.time,
            "bugs": total.bugs,

            "functions": [
                HalsteadEngine._serialize_function(function)
                for function in result.functions
            ],
        }

    @staticmethod
    def _serialize_function(function) -> dict:
        """
        Convert a Radon Halstead function result
        into a serializable dictionary.

        Radon's h_visit().functions returns tuples
        in the following form:

            (function_name, HalsteadReport)
        """

        name, report = function

        return {
            "name": name,

            "volume": report.volume,

            "vocabulary": (
                    report.h1
                    + report.h2
            ),

            "length": (
                    report.N1
                    + report.N2
            ),

            "distinct_operators": report.h1,
            "distinct_operands": report.h2,

            "total_operators": report.N1,
            "total_operands": report.N2,

            "calculated_length": report.calculated_length,
            "difficulty": report.difficulty,
            "effort": report.effort,
            "time": report.time,
            "bugs": report.bugs,
        }