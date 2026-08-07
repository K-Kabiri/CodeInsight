from pathlib import Path

from .python_loader import PythonLoader
from .zip_loader import ZipLoader


def get_loader(file_path):

    suffix = Path(file_path).suffix.lower()

    if suffix == ".zip":
        return ZipLoader(file_path)

    if suffix == ".py":
        return PythonLoader(file_path)

    raise ValueError(f"Unsupported file type: {suffix}")