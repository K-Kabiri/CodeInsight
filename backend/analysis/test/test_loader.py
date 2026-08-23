import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase

from analysis.loaders import get_loader
from analysis.loaders.python_loader import PythonLoader
from analysis.loaders.zip_loader import ZipLoader


class LoaderTest(SimpleTestCase):

    def test_python_loader(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            python_file = Path(temp_dir) / "main.py"

            python_file.write_text(
                "print('Hello')\n",
                encoding="utf-8",
            )

            loader = PythonLoader(python_file)

            self.assertEqual(
                loader.scope,
                "single_file",
            )

            files = loader.load()

            self.assertEqual(len(files), 1)
            self.assertEqual(files[0], python_file)

    def test_zip_loader(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            temp_dir = Path(temp_dir)

            project_dir = temp_dir / "project"
            project_dir.mkdir()

            main_file = project_dir / "main.py"
            utils_file = project_dir / "utils.py"
            readme_file = project_dir / "README.md"

            main_file.write_text(
                "print('main')\n",
                encoding="utf-8",
            )

            utils_file.write_text(
                "def hello():\n    pass\n",
                encoding="utf-8",
            )

            readme_file.write_text(
                "# Test Project",
                encoding="utf-8",
            )

            zip_path = temp_dir / "project.zip"

            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.write(
                    main_file,
                    "project/main.py",
                )
                zip_file.write(
                    utils_file,
                    "project/utils.py",
                )
                zip_file.write(
                    readme_file,
                    "project/README.md",
                )

            loader = ZipLoader(zip_path)

            self.assertEqual(
                loader.scope,
                "project",
            )

            files = loader.load()

            self.assertEqual(len(files), 2)

            file_names = {file.name for file in files}

            self.assertEqual(
                file_names,
                {"main.py", "utils.py"},
            )

            loader.cleanup()

            # The extracted temp directory is gone after cleanup.
            for file in files:
                self.assertFalse(
                    file.exists(),
                    f"{file} should be removed by cleanup()",
                )

    def test_zip_loader_cleanup_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            zip_path = Path(temp_dir) / "single.zip"

            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr(
                    "main.py",
                    "print('hello')\n",
                )

            loader = ZipLoader(zip_path)

            loader.load()

            loader.cleanup()
            loader.cleanup()  # must not raise

            self.assertIsNone(loader._temp_dir)

    def test_one_file_zip_is_project_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            zip_path = Path(temp_dir) / "single.zip"

            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr(
                    "main.py",
                    "print('hello')\n",
                )

            loader = ZipLoader(zip_path)

            self.assertEqual(
                loader.scope,
                "project",
            )

            self.assertEqual(
                len(loader.load()),
                1,
            )

    def test_loader_factory_for_python_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            python_file = Path(temp_dir) / "main.py"

            python_file.write_text(
                "print('Hello')\n",
                encoding="utf-8",
            )

            loader = get_loader(python_file)

            self.assertIsInstance(
                loader,
                PythonLoader,
            )

    def test_loader_factory_for_zip_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            zip_path = Path(temp_dir) / "project.zip"

            with zipfile.ZipFile(zip_path, "w"):
                pass

            loader = get_loader(zip_path)

            self.assertIsInstance(
                loader,
                ZipLoader,
            )