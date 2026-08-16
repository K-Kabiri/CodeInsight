from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
from radon.metrics import h_visit

from analysis.engines.halstead import HalsteadEngine


class HalsteadEngineTest(SimpleTestCase):

    def setUp(self):
        self.engine = HalsteadEngine()
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

    # BASIC
    def test_empty_file_has_zero_volume(self):
        path = self._create_python_file("")

        result = self.engine.calculate_detailed([path])

        self.assertEqual(
            result["total"],
            0,
        )

        self.assertEqual(
            result["average"],
            0.0,
        )

        self.assertEqual(
            result["files"][0]["volume"],
            0,
        )

    def test_empty_project_has_zero_volume(self):
        result = self.engine.calculate_detailed([])

        self.assertEqual(
            result["total"],
            0,
        )

        self.assertEqual(
            result["average"],
            0.0,
        )

        self.assertEqual(
            result["files"],
            [],
        )

    # RADON CONSISTENCY
    def test_volume_matches_radon(self):
        source = """
def add(a, b):
    return a + b
"""

        path = self._create_python_file(source)

        expected = h_visit(source).total.volume
        actual = self.engine.calculate([path])

        self.assertEqual(
            actual,
            expected,
        )

    def test_detailed_metrics_match_radon(self):
        source = """
def calculate(a, b):
    result = a + b
    return result
"""

        path = self._create_python_file(source)

        expected = h_visit(source).total
        result = self.engine.calculate_detailed([path])

        file_result = result["files"][0]

        self.assertEqual(
            file_result["volume"],
            expected.volume,
        )

        self.assertEqual(
            file_result["vocabulary"],
            expected.h1 + expected.h2,
        )

        self.assertEqual(
            file_result["length"],
            expected.N1 + expected.N2,
        )

        self.assertEqual(
            file_result["distinct_operators"],
            expected.h1,
        )

        self.assertEqual(
            file_result["distinct_operands"],
            expected.h2,
        )

        self.assertEqual(
            file_result["total_operators"],
            expected.N1,
        )

        self.assertEqual(
            file_result["total_operands"],
            expected.N2,
        )

        self.assertEqual(
            file_result["calculated_length"],
            expected.calculated_length,
        )

        self.assertEqual(
            file_result["difficulty"],
            expected.difficulty,
        )

        self.assertEqual(
            file_result["effort"],
            expected.effort,
        )

        self.assertEqual(
            file_result["time"],
            expected.time,
        )

        self.assertEqual(
            file_result["bugs"],
            expected.bugs,
        )

    # FUNCTIONS
    def test_functions_are_reported(self):
        source = """
def first(a):
    return a + 1


def second(b):
    return b * 2
"""

        path = self._create_python_file(source)

        result = self.engine.calculate_detailed([path])

        functions = result["files"][0]["functions"]

        self.assertEqual(
            len(functions),
            2,
        )

        names = {
            function["name"]
            for function in functions
        }

        self.assertEqual(
            names,
            {
                "first",
                "second",
            },
        )

    def test_function_metrics_match_radon(self):
        source = """
def add(a, b):
    result = a + b
    return result
"""

        path = self._create_python_file(source)

        expected = h_visit(source).functions
        result = self.engine.calculate_detailed([path])

        functions = result["files"][0]["functions"]

        self.assertEqual(
            len(functions),
            len(expected),
        )

        actual = functions[0]

        expected_name, expected_function = expected[0]

        self.assertEqual(
            actual["name"],
            expected_name,
        )

        self.assertEqual(
            actual["volume"],
            expected_function.volume,
        )

        self.assertEqual(
            actual["vocabulary"],
            expected_function.h1
            + expected_function.h2,
        )

        self.assertEqual(
            actual["length"],
            expected_function.N1
            + expected_function.N2,
        )

        self.assertEqual(
            actual["distinct_operators"],
            expected_function.h1,
        )

        self.assertEqual(
            actual["distinct_operands"],
            expected_function.h2,
        )

        self.assertEqual(
            actual["total_operators"],
            expected_function.N1,
        )

        self.assertEqual(
            actual["total_operands"],
            expected_function.N2,
        )

        self.assertEqual(
            actual["calculated_length"],
            expected_function.calculated_length,
        )

        self.assertEqual(
            actual["difficulty"],
            expected_function.difficulty,
        )

        self.assertEqual(
            actual["effort"],
            expected_function.effort,
        )

        self.assertEqual(
            actual["time"],
            expected_function.time,
        )

        self.assertEqual(
            actual["bugs"],
            expected_function.bugs,
        )

    # MULTIPLE FUNCTIONS
    def test_multiple_functions_have_independent_metrics(self):
        source = """
def add(a, b):
    return a + b


def multiply(a, b):
    return a * b
"""

        path = self._create_python_file(source)

        expected = h_visit(source)
        result = self.engine.calculate_detailed([path])

        functions = result["files"][0]["functions"]

        self.assertEqual(
            len(functions),
            2,
        )

        expected_functions = {
            name: report
            for name, report in expected.functions
        }

        for function in functions:
            expected_function = expected_functions[
                function["name"]
            ]

            self.assertEqual(
                function["volume"],
                expected_function.volume,
            )

            self.assertEqual(
                function["vocabulary"],
                expected_function.h1
                + expected_function.h2,
            )

            self.assertEqual(
                function["length"],
                expected_function.N1
                + expected_function.N2,
            )

            self.assertEqual(
                function["distinct_operators"],
                expected_function.h1,
            )

            self.assertEqual(
                function["distinct_operands"],
                expected_function.h2,
            )

            self.assertEqual(
                function["total_operators"],
                expected_function.N1,
            )

            self.assertEqual(
                function["total_operands"],
                expected_function.N2,
            )

    # MULTIPLE FILES
    def test_multiple_files_are_aggregated(self):
        first_source = """
def first(a):
    return a + 1
"""

        second_source = """
def second(b):
    return b * 2
"""

        first = self._create_python_file(
            first_source,
            "first.py",
        )

        second = self._create_python_file(
            second_source,
            "second.py",
        )

        expected_first = h_visit(
            first_source
        ).total.volume

        expected_second = h_visit(
            second_source
        ).total.volume

        result = self.engine.calculate_detailed(
            [first, second]
        )

        expected_total = (
                expected_first
                + expected_second
        )

        self.assertEqual(
            result["total"],
            expected_total,
        )

        self.assertEqual(
            result["average"],
            expected_total / 2,
        )

        self.assertEqual(
            len(result["files"]),
            2,
        )

    # AVERAGE
    def test_average_is_calculated_from_file_volumes(self):
        first_source = """
def first(a):
    return a + 1
"""

        second_source = """
def second(b):
    return b * 2
"""

        first = self._create_python_file(
            first_source,
            "first.py",
        )

        second = self._create_python_file(
            second_source,
            "second.py",
        )

        first_volume = h_visit(
            first_source
        ).total.volume

        second_volume = h_visit(
            second_source
        ).total.volume

        result = self.engine.calculate_detailed(
            [first, second]
        )

        expected_total = (
                first_volume
                + second_volume
        )

        expected_average = (
                expected_total / 2
        )

        self.assertEqual(
            result["total"],
            expected_total,
        )

        self.assertEqual(
            result["average"],
            expected_average,
        )

    # FILE INFORMATION
    def test_file_path_is_reported(self):
        path = self._create_python_file(
            """
def foo():
    return 1
"""
        )

        result = self.engine.calculate_detailed([path])

        file_result = result["files"][0]

        self.assertEqual(
            file_result["file"],
            str(path),
        )

    def test_file_volume_is_reported(self):
        source = """
def foo(a):
    return a + 1
"""

        path = self._create_python_file(source)

        expected = h_visit(source).total.volume

        result = self.engine.calculate_detailed([path])

        self.assertEqual(
            result["files"][0]["volume"],
            expected,
        )

    # HALSTEAD COMPONENTS
    def test_halstead_components_are_consistent(self):
        source = """
def calculate(a, b):
    result = a + b
    return result
"""

        path = self._create_python_file(source)

        result = self.engine.calculate_detailed([path])

        file_result = result["files"][0]

        self.assertEqual(
            file_result["vocabulary"],
            (
                    file_result["distinct_operators"]
                    + file_result["distinct_operands"]
            ),
        )

        self.assertEqual(
            file_result["length"],
            (
                    file_result["total_operators"]
                    + file_result["total_operands"]
            ),
        )

    # CALCULATE VS DETAILED
    def test_calculate_returns_detailed_total(self):
        source = """
def foo(a, b):
    return a + b
"""

        path = self._create_python_file(source)

        detailed = self.engine.calculate_detailed([path])
        simple = self.engine.calculate([path])

        self.assertEqual(
            simple,
            detailed["total"],
        )
