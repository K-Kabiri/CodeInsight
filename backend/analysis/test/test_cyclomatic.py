from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from analysis.engines.cyclomatic import (
    CyclomaticComplexityEngine,
)


class CyclomaticComplexityEngineTest(SimpleTestCase):

    def setUp(self):
        self.engine = CyclomaticComplexityEngine()
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

    def test_empty_file_has_zero_complexity(self):
        path = self._create_python_file("")

        self.assertEqual(
            self.engine.calculate([path]),
            0,
        )

    def test_simple_function_has_complexity_one(self):
        path = self._create_python_file(
            """
def foo():
    return 1
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            1,
        )

    def test_if_adds_one(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
    return 0
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_if_else_does_not_add_extra_complexity(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
    else:
        return 0
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_elif_adds_one(self):
        path = self._create_python_file(
            """
def foo(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    return 0
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            3,
        )

    def test_for_adds_one(self):
        path = self._create_python_file(
            """
def foo(items):
    for item in items:
        print(item)
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_while_adds_one(self):
        path = self._create_python_file(
            """
def foo(x):
    while x:
        x -= 1
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_except_adds_complexity(self):
        path = self._create_python_file(
            """
def foo():
    try:
        return 1
    except ValueError:
        return 0
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["blocks"][0]

        self.assertEqual(
            function["complexity"],
            2,
        )

    def test_boolean_expression_adds_complexity(self):
        path = self._create_python_file(
            """
def foo(a, b):
    if a and b:
        return True
    return False
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["blocks"][0]

        self.assertEqual(
            function["complexity"],
            3,
        )

    def test_nested_conditions_are_counted(self):
        path = self._create_python_file(
            """
def foo(a, b):
    if a:
        if b:
            return True
    return False
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["blocks"][0]

        self.assertEqual(
            function["complexity"],
            3,
        )

    def test_multiple_functions_are_reported_independently(self):
        path = self._create_python_file(
            """
def first(x):
    if x:
        return 1
    return 0


def second(x):
    if x:
        return 1

    if x > 10:
        return 2

    return 0
"""
        )

        result = self.engine.calculate_detailed([path])

        blocks = result["files"][0]["blocks"]

        self.assertEqual(
            len(blocks),
            2,
        )

        self.assertEqual(
            blocks[0]["name"],
            "first",
        )

        self.assertEqual(
            blocks[0]["complexity"],
            2,
        )

        self.assertEqual(
            blocks[1]["name"],
            "second",
        )

        self.assertEqual(
            blocks[1]["complexity"],
            3,
        )

    def test_async_function_is_calculated(self):
        path = self._create_python_file(
            """
async def fetch_data(condition):
    if condition:
        return 1
    return 0
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["blocks"][0]

        self.assertEqual(
            function["name"],
            "fetch_data",
        )

        self.assertEqual(
            function["complexity"],
            2,
        )

    def test_class_and_methods_are_reported(self):
        path = self._create_python_file(
            """
class User:

    def is_active(self, active):
        if active:
            return True
        return False

    def is_admin(self, admin):
        if admin:
            return True
        return False
"""
        )

        result = self.engine.calculate_detailed([path])

        blocks = result["files"][0]["blocks"]

        class_block = next(
            block
            for block in blocks
            if block["type"] == "class"
        )

        self.assertEqual(
            class_block["name"],
            "User",
        )

        self.assertEqual(
            len(class_block["methods"]),
            2,
        )

        method_names = {
            method["name"]
            for method in class_block["methods"]
        }

        self.assertEqual(
            method_names,
            {"is_active", "is_admin"},
        )

    def test_rank_is_calculated(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
    return 0
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["blocks"][0]

        self.assertEqual(
            function["complexity"],
            2,
        )

        self.assertEqual(
            function["rank"],
            "A",
        )

    def test_multiple_files_are_aggregated(self):
        first = self._create_python_file(
            """
def first(x):
    if x:
        return 1
    return 0
""",
            "first.py",
        )

        second = self._create_python_file(
            """
def second(x):
    if x:
        return 1

    if x > 10:
        return 2

    return 0
""",
            "second.py",
        )

        result = self.engine.calculate_detailed(
            [first, second]
        )

        self.assertEqual(
            len(result["files"]),
            2,
        )

        self.assertEqual(
            result["total"],
            5,
        )

    def test_average_complexity_is_calculated(self):
        first = self._create_python_file(
            """
def first():
    return 1
""",
            "first.py",
        )

        second = self._create_python_file(
            """
def second(x):
    if x:
        return 1
    return 0
""",
            "second.py",
        )

        result = self.engine.calculate_detailed(
            [first, second]
        )

        self.assertEqual(
            result["total"],
            3,
        )

        self.assertEqual(
            result["average"],
            1.5,
        )

    def test_line_information_is_preserved(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
    return 0
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["blocks"][0]

        self.assertIsNotNone(
            function["lineno"]
        )

        self.assertIsNotNone(
            function["endline"]
        )

        self.assertGreaterEqual(
            function["endline"],
            function["lineno"],
        )