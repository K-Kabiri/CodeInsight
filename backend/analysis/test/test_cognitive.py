from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from analysis.engines.cognitive import (
    CognitiveComplexityEngine,
)


class CognitiveComplexityEngineTest(SimpleTestCase):

    def setUp(self):
        self.engine = CognitiveComplexityEngine()
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

    # =========================================================
    # Basic
    # =========================================================

    def test_empty_file(self):
        path = self._create_python_file("")

        self.assertEqual(
            self.engine.calculate([path]),
            0,
        )

    def test_simple_function_has_zero_complexity(self):
        path = self._create_python_file(
            """
def foo():
    return 1
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            0,
        )

    # =========================================================
    # IF / ELIF / ELSE
    # =========================================================

    def test_if_adds_one(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            1,
        )

    def test_if_else_chain(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
    else:
        return 0
"""
        )

        # if = 1
        # else = 1
        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_if_elif_else_chain(self):
        path = self._create_python_file(
            """
def foo(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    else:
        return 0
"""
        )

        # if   = 1
        # elif = 1
        # else = 1
        self.assertEqual(
            self.engine.calculate([path]),
            3,
        )

    # =========================================================
    # Nesting
    # =========================================================

    def test_nested_if_increases_complexity(self):
        path = self._create_python_file(
            """
def foo(a, b):
    if a:
        if b:
            return 1
"""
        )

        # outer if = 1
        # inner if = 2
        self.assertEqual(
            self.engine.calculate([path]),
            3,
        )

    def test_deep_nesting(self):
        path = self._create_python_file(
            """
def foo(a, b, c):
    if a:
        if b:
            if c:
                return 1
"""
        )

        # 1 + 2 + 3
        self.assertEqual(
            self.engine.calculate([path]),
            6,
        )

    def test_max_nesting_is_reported(self):
        path = self._create_python_file(
            """
def foo(a, b):
    if a:
        if b:
            return 1
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["functions"][0]

        self.assertEqual(
            function["max_nesting"],
            2,
        )

    # =========================================================
    # LOOPS
    # =========================================================

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
            1,
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
            1,
        )

    def test_nested_loops(self):
        path = self._create_python_file(
            """
def foo(items):
    for item in items:
        while item:
            process(item)
"""
        )

        # for   = 1
        # while = 2
        self.assertEqual(
            self.engine.calculate([path]),
            3,
        )

    def test_async_for(self):
        path = self._create_python_file(
            """
async def foo(items):
    async for item in items:
        process(item)
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            1,
        )

    # =========================================================
    # BOOLEAN EXPRESSIONS
    # =========================================================

    def test_single_boolean_sequence(self):
        path = self._create_python_file(
            """
def foo(a, b, c):
    if a and b and c:
        return True
"""
        )

        # if = 1
        # a and b and c = one boolean sequence = 1
        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_or_boolean_sequence(self):
        path = self._create_python_file(
            """
def foo(a, b, c):
    if a or b or c:
        return True
"""
        )

        # if = 1
        # boolean sequence = 1
        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_mixed_boolean_sequences(self):
        path = self._create_python_file(
            """
def foo(a, b, c):
    if a and b or c:
        return True
"""
        )

        # if = 1
        # and sequence = 1
        # or sequence = 1
        self.assertEqual(
            self.engine.calculate([path]),
            3,
        )

    def test_nested_boolean_sequences(self):
        path = self._create_python_file(
            """
def foo(a, b, c, d):
    if (a and b) or (c and d):
        return True
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["functions"][0]

        boolean_contributions = [
            contribution
            for contribution in function["contributions"]
            if contribution["type"] == "boolean_sequence"
        ]

        self.assertEqual(
            len(boolean_contributions),
            3,
        )

    # =========================================================
    # EXCEPTION HANDLING
    # =========================================================

    def test_except_adds_one(self):
        path = self._create_python_file(
            """
def foo():
    try:
        operation()
    except ValueError:
        handle_error()
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            1,
        )

    def test_try_does_not_add_complexity(self):
        path = self._create_python_file(
            """
def foo():
    try:
        operation()
    finally:
        cleanup()
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            0,
        )

    # =========================================================
    # CONDITIONAL EXPRESSION
    # =========================================================

    def test_ternary_adds_one(self):
        path = self._create_python_file(
            """
def foo(x):
    return 1 if x else 0
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            1,
        )

    # =========================================================
    # BREAK / CONTINUE
    # =========================================================

    def test_break_adds_one(self):
        path = self._create_python_file(
            """
def foo(items):
    for item in items:
        if item:
            break
"""
        )

        # for = 1
        # if = 2
        # break = 1
        self.assertEqual(
            self.engine.calculate([path]),
            4,
        )

    def test_continue_adds_one(self):
        path = self._create_python_file(
            """
def foo(items):
    for item in items:
        if item:
            continue
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            4,
        )

    # =========================================================
    # RECURSION
    # =========================================================

    def test_recursive_call_adds_one(self):
        path = self._create_python_file(
            """
def factorial(n):
    if n <= 1:
        return 1

    return n * factorial(n - 1)
"""
        )

        # if = 1
        # recursion = 1
        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    def test_non_recursive_call_is_free(self):
        path = self._create_python_file(
            """
def foo():
    helper()
"""
        )

        self.assertEqual(
            self.engine.calculate([path]),
            0,
        )

    # =========================================================
    # MATCH
    # =========================================================

    def test_match_adds_one(self):
        path = self._create_python_file(
            """
def foo(value):
    match value:
        case 1:
            return "one"
        case 2:
            return "two"
"""
        )

        # Entire match structure = 1
        self.assertEqual(
            self.engine.calculate([path]),
            1,
        )

    def test_match_guard_adds_one(self):
        path = self._create_python_file(
            """
def foo(value):
    match value:
        case x if x > 10:
            return "large"
"""
        )

        # match = 1
        # guard = 1
        self.assertEqual(
            self.engine.calculate([path]),
            2,
        )

    # =========================================================
    # FUNCTIONS
    # =========================================================

    def test_multiple_functions_are_independent(self):
        path = self._create_python_file(
            """
def first(x):
    if x:
        return 1


def second(x):
    if x:
        if x > 10:
            return 2
"""
        )

        result = self.engine.calculate_detailed([path])

        functions = result["files"][0]["functions"]

        self.assertEqual(
            len(functions),
            2,
        )

        first = next(
            function
            for function in functions
            if function["name"] == "first"
        )

        second = next(
            function
            for function in functions
            if function["name"] == "second"
        )

        self.assertEqual(
            first["complexity"],
            1,
        )

        self.assertEqual(
            second["complexity"],
            3,
        )

    def test_nested_function_has_independent_nesting(self):
        path = self._create_python_file(
            """
def outer(x):

    if x:

        def inner(y):
            if y:
                return 1

        return inner(x)
"""
        )

        result = self.engine.calculate_detailed([path])

        functions = result["files"][0]["functions"]

        outer = next(
            function
            for function in functions
            if function["name"] == "outer"
        )

        inner = next(
            function
            for function in functions
            if function["name"] == "inner"
        )

        self.assertEqual(
            outer["complexity"],
            1,
        )

        self.assertEqual(
            inner["complexity"],
            1,
        )

    # =========================================================
    # CLASS / METHODS
    # =========================================================

    def test_class_methods_are_reported(self):
        path = self._create_python_file(
            """
class User:

    def is_active(self, active):
        if active:
            return True

    def is_admin(self, admin):
        if admin:
            return True
"""
        )

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
                "is_active",
                "is_admin",
            },
        )

        for function in functions:
            self.assertEqual(
                function["type"],
                "method",
            )

            self.assertEqual(
                function["classname"],
                "User",
            )

    # =========================================================
    # MULTIPLE FILES
    # =========================================================

    def test_multiple_files_are_aggregated(self):
        first = self._create_python_file(
            """
def first(x):
    if x:
        return 1
""",
            "first.py",
        )

        second = self._create_python_file(
            """
def second(x):
    if x:
        if x > 10:
            return 2
""",
            "second.py",
        )

        result = self.engine.calculate_detailed(
            [first, second]
        )

        self.assertEqual(
            result["total"],
            4,
        )

        self.assertEqual(
            result["function_count"],
            2,
        )

    # =========================================================
    # AVERAGE
    # =========================================================

    def test_average_complexity(self):
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
""",
            "second.py",
        )

        result = self.engine.calculate_detailed(
            [first, second]
        )

        self.assertEqual(
            result["total"],
            1,
        )

        self.assertEqual(
            result["average"],
            0.5,
        )

    # =========================================================
    # DETAILED CONTRIBUTIONS
    # =========================================================

    def test_contributions_are_recorded(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["functions"][0]

        self.assertTrue(
            function["contributions"]
        )

        contribution = function["contributions"][0]

        self.assertEqual(
            contribution["type"],
            "if",
        )

        self.assertEqual(
            contribution["increment"],
            1,
        )

        self.assertEqual(
            contribution["lineno"],
            3,
        )

    # =========================================================
    # LINE INFORMATION
    # =========================================================

    def test_line_information_is_available(self):
        path = self._create_python_file(
            """
def foo(x):
    if x:
        return 1
"""
        )

        result = self.engine.calculate_detailed([path])

        function = result["files"][0]["functions"][0]

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