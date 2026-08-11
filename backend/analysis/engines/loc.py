from dataclasses import asdict, dataclass
from pathlib import Path

from radon.raw import analyze

from .base import BaseMetricEngine


@dataclass(frozen=True)
class LOCFileMetrics:
    """
    Raw source-code metrics calculated by Radon for a single file.
    """

    loc: int
    lloc: int
    sloc: int
    comments: int
    single_comments: int
    multi: int
    blank: int

    @property
    def comment_ratio(self) -> float:
        """
        Ratio of comment lines to physical LOC.
        """
        if self.loc == 0:
            return 0.0

        return self.comments / self.loc

    def to_dict(self) -> dict:
        """
        Convert metrics to a serializable dictionary.
        """
        return {
            **asdict(self),
            "comment_ratio": self.comment_ratio,
        }


class LOCEngine(BaseMetricEngine):

    def calculate(self, python_files: list[Path]) -> int:
        """
        Return the total physical LOC across all Python files.

        LOC follows Radon's raw metric definition.
        """
        metrics = self.calculate_detailed(python_files)

        return metrics["loc"]

    def calculate_detailed(
            self,
            python_files: list[Path],
    ) -> dict:
        """
        Calculate all Radon raw metrics.

        Returns both project-level totals and per-file metrics.
        """

        file_metrics = []

        for file_path in python_files:
            metrics = self._analyze_file(file_path)

            file_metrics.append(
                {
                    "file": str(file_path),
                    **metrics.to_dict(),
                }
            )

        totals = {
            "loc": sum(item["loc"] for item in file_metrics),
            "lloc": sum(item["lloc"] for item in file_metrics),
            "sloc": sum(item["sloc"] for item in file_metrics),
            "comments": sum(
                item["comments"]
                for item in file_metrics
            ),
            "single_comments": sum(
                item["single_comments"]
                for item in file_metrics
            ),
            "multi": sum(
                item["multi"]
                for item in file_metrics
            ),
            "blank": sum(
                item["blank"]
                for item in file_metrics
            ),
        }

        totals["comment_ratio"] = (
            totals["comments"] / totals["loc"]
            if totals["loc"] > 0
            else 0.0
        )

        return {
            "totals": totals,
            "files": file_metrics,
        }

    @staticmethod
    def _analyze_file(
            file_path: Path,
    ) -> LOCFileMetrics:
        source_code = file_path.read_text(
            encoding="utf-8"
        )

        result = analyze(source_code)

        return LOCFileMetrics(
            loc=result.loc,
            lloc=result.lloc,
            sloc=result.sloc,
            comments=result.comments,
            single_comments=result.single_comments,
            multi=result.multi,
            blank=result.blank,
        )
