from pathlib import Path
import tempfile
import zipfile

from .base import BaseLoader


class ZipLoader(BaseLoader):

    def __init__(self, zip_path):
        self.zip_path = Path(zip_path)

    def load(self):

        temp_dir = tempfile.mkdtemp()

        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        python_files = []

        for path in Path(temp_dir).rglob("*.py"):
            python_files.append(path)

        return python_files