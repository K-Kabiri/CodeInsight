from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from analysis.engines.loc import LOCEngine


class LOCEngineTest(SimpleTestCase):

    def setUp(self):
        self.engine = LOCEngine()
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_python_file(
            self,
            source: str,
            filename: str = "test.py",
    ) -> Path:
        path = Path(self.temp_dir.name) / filename
        path.write_text(
            source,
            encoding="utf-8",
        )

        return path

    def test_empty_file(self):
        path = self._create_python_file("")

        self.assertEqual(
            self.engine.calculate([path]),
            0,
        )

    def test_loc_is_calculated(self):
        source = """\
x = 1
y = 2
z = 3
"""

        path = self._create_python_file(source)

        self.assertEqual(
            self.engine.calculate([path]),
            3,
        )

    def test_detailed_metrics_are_available(self):
        source = """\
# comment

x = 1

y = 2
"""

        path = self._create_python_file(source)

        result = self.engine.calculate_detailed([path])

        self.assertIn("totals", result)
        self.assertIn("files", result)

        totals = result["totals"]

        self.assertIn("loc", totals)
        self.assertIn("lloc", totals)
        self.assertIn("sloc", totals)
        self.assertIn("comments", totals)
        self.assertIn("single_comments", totals)
        self.assertIn("multi", totals)
        self.assertIn("blank", totals)

    def test_file_level_metrics_are_available(self):
        source = """\
x = 1
y = 2
"""

        path = self._create_python_file(source)

        result = self.engine.calculate_detailed([path])

        self.assertEqual(
            len(result["files"]),
            1,
        )

        file_result = result["files"][0]

        self.assertEqual(
            file_result["file"],
            str(path),
        )

        self.assertIn(
            "loc",
            file_result,
        )

    def test_multiple_files_are_aggregated(self):
        first = self._create_python_file(
            "x = 1\n",
            "first.py",
        )

        second = self._create_python_file(
            "x = 1\ny = 2\n",
            "second.py",
        )

        result = self.engine.calculate_detailed(
            [first, second]
        )

        self.assertEqual(
            result["totals"]["loc"],
            3,
        )

        self.assertEqual(
            len(result["files"]),
            2,
        )

    def test_comment_ratio_is_available(self):
        source = """\
# comment
x = 1
"""

        path = self._create_python_file(source)

        result = self.engine.calculate_detailed([path])

        self.assertGreaterEqual(
            result["totals"]["comment_ratio"],
            0.0,
        )

        self.assertLessEqual(
            result["totals"]["comment_ratio"],
            1.0,
        )
