from abc import ABC, abstractmethod
from pathlib import Path


class BaseMetricEngine(ABC):

    @abstractmethod
    def calculate(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> float:
        """
        Calculate the metric value for the given Python files.

        `scope` is the Input scope (`"single_file"` or
        `"project"`), passed explicitly by the service. It is
        additive: existing engines ignore it, while
        dependency-based metrics use it to report
        `scope`/`completeness` honestly (ADR-0001).
        """
        pass

    def calculate_detailed(
            self,
            python_files: list[Path],
            scope: str | None = None,
    ) -> dict | None:
        """
        Calculate per-file, per-class detail for the metric.

        Engines that produce explainable detail override this
        method; the default returns None (no detail).
        """
        return None