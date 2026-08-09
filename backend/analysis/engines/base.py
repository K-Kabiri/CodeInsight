from abc import ABC, abstractmethod
from pathlib import Path


class BaseMetricEngine(ABC):

    @abstractmethod
    def calculate(self, python_files: list[Path]) -> float:
        """
        Calculate the metric value for the given Python files.
        """
        pass