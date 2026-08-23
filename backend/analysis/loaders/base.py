from abc import ABC, abstractmethod
from pathlib import Path


class BaseLoader(ABC):
    """
    Loads the Python files of an Input.

    Each loader represents one Input kind and therefore
    declares the Input `scope` it corresponds to
    (CONTEXT.md): `single_file` for a lone `.py` file,
    `project` for a ZIP — even a ZIP containing a single
    file.
    """

    scope: str = ""

    @abstractmethod
    def load(self) -> list[Path]:
        pass

    def cleanup(self) -> None:
        """
        Release resources the loader created while loading (e.g. the
        temporary directory a ZIP was extracted into).

        The default is a no-op: `PythonLoader` only wraps a path the
        caller owns. `ZipLoader` overrides it. The service calls this
        in a `finally` after the Analysis finishes.
        """
        pass
