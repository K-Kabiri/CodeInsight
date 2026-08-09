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

    def __init__(self, zip_path):
        self.zip_path = Path(zip_path)

    def load(self) -> list[Path]:
        temp_dir = tempfile.mkdtemp()

        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        python_files = []

        for path in Path(temp_dir).rglob("*.py"):

            if any(part.startswith(".") for part in path.parts):
                continue

            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue

            python_files.append(path)

        return python_files