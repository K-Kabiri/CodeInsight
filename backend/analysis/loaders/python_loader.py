from pathlib import Path

from .base import BaseLoader


class PythonLoader(BaseLoader):

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def load(self):
        return [self.file_path]