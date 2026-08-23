from pathlib import Path
import tempfile
import zipfile

from .base import BaseLoader


IGNORED_DIRECTORIES = {
    "__pycache__",
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "site-packages",
    "node_modules",
    ".idea",
    ".vscode",
}


class ZipLoader(BaseLoader):

    scope = "project"

    def __init__(self, zip_path):
        self.zip_path = Path(zip_path)
        self._temp_dir = None

    def load(self) -> list[Path]:
        # The extracted files must stay readable for the whole
        # Analysis, so the TemporaryDirectory lives on the loader and
        # is removed by `cleanup()` (called by the service in a
        # `finally`) — never at the end of `load()`.
        self._temp_dir = tempfile.TemporaryDirectory()

        temp_dir = Path(self._temp_dir.name)

        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            self._safe_extract(zip_ref, temp_dir)

        python_files = []

        for path in temp_dir.rglob("*.py"):

            if any(part.startswith(".") for part in path.parts):
                continue

            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue

            python_files.append(path)

        return python_files

    def cleanup(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

    @staticmethod
    def _safe_extract(zip_ref: zipfile.ZipFile, destination: Path) -> None:
        destination = destination.resolve()

        for member in zip_ref.infolist():
            member_path = (destination / member.filename).resolve()

            if not member_path.is_relative_to(destination):
                raise ValueError(
                    f"Unsafe ZIP file path: {member.filename}"
                )

        zip_ref.extractall(destination)
