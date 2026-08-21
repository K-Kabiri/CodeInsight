import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from analysis.engines import ENGINE_REGISTRY, get_engine
from analysis.engines.code_smells import CodeSmellsEngine
from analysis.models import MetricDefinition


def analyze(source: str) -> dict:
    """Run the engine over a single source string in a temp file."""
    with tempfile.NamedTemporaryFile(
            suffix=".py",
            delete=False,
            mode="w",
            encoding="utf-8",
    ) as temp_file:
        temp_file.write(source)
        path = Path(temp_file.name)

    try:
        return CodeSmellsEngine().calculate_detailed(
            [path],
            scope="single_file",
        )
    finally:
        path.unlink()


def smell_types(detail: dict) -> set[str]:
    return set(detail["by_type"].keys())


class LongMethodTest(SimpleTestCase):

    def test_fires_when_body_is_31_lines(self):
        source = (
            "def long():\n"
            + "".join(
                f"    x{i} = 0\n"
                for i in range(31)
            )
        )

        detail = analyze(source)

        self.assertIn(
            "long-method",
            smell_types(detail),
        )

    def test_does_not_fire_when_body_is_30_lines(self):
        source = (
            "def ok():\n"
            + "".join(
                f"    x{i} = 0\n"
                for i in range(30)
            )
        )

        detail = analyze(source)

        self.assertNotIn(
            "long-method",
            smell_types(detail),
        )

    def test_nested_function_is_a_separate_candidate(self):
        # A long nested function must be flagged even though the
        # outer function is short.
        source = (
            "def outer():\n"
            "    def inner():\n"
            + "".join(
                f"        x{i} = 0\n"
                for i in range(31)
            )
            + "    return inner\n"
        )

        detail = analyze(source)

        self.assertIn(
            "long-method",
            smell_types(detail),
        )


class LargeClassTest(SimpleTestCase):

    def test_fires_when_class_body_is_201_lines(self):
        source = (
            "class Big:\n"
            "    def m(self):\n"
            + "".join(
                f"        x{i} = 0\n"
                for i in range(200)
            )
        )

        detail = analyze(source)

        self.assertIn(
            "large-class",
            smell_types(detail),
        )

    def test_fires_when_class_has_16_methods(self):
        source = (
            "class Big:\n"
            + "".join(
                f"    def m{i}(self): pass\n"
                for i in range(16)
            )
        )

        detail = analyze(source)

        self.assertIn(
            "large-class",
            smell_types(detail),
        )

    def test_does_not_fire_when_class_body_is_200_lines(self):
        source = (
            "class Big:\n"
            "    def m(self):\n"
            + "".join(
                f"        x{i} = 0\n"
                for i in range(199)
            )
        )

        detail = analyze(source)

        self.assertNotIn(
            "large-class",
            smell_types(detail),
        )

    def test_does_not_fire_when_class_has_15_methods(self):
        source = (
            "class Big:\n"
            + "".join(
                f"    def m{i}(self): pass\n"
                for i in range(15)
            )
        )

        detail = analyze(source)

        self.assertNotIn(
            "large-class",
            smell_types(detail),
        )


class DeepNestingTest(SimpleTestCase):

    def test_fires_at_depth_5(self):
        source = (
            "def deep():\n"
            "    if a:\n"
            "        if b:\n"
            "            if c:\n"
            "                if d:\n"
            "                    x = 1\n"
        )

        detail = analyze(source)

        self.assertIn(
            "deep-nesting",
            smell_types(detail),
        )

    def test_does_not_fire_at_depth_4(self):
        source = (
            "def ok():\n"
            "    if a:\n"
            "        if b:\n"
            "            if c:\n"
            "                x = 1\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "deep-nesting",
            smell_types(detail),
        )

    def test_else_branch_counts_as_nesting(self):
        source = (
            "def deep():\n"
            "    if a:\n"
            "        if b:\n"
            "            if c:\n"
            "                if d:\n"
            "                    x = 1\n"
            "                else:\n"
            "                    y = 2\n"
        )

        detail = analyze(source)

        self.assertIn(
            "deep-nesting",
            smell_types(detail),
        )


class LongParameterListTest(SimpleTestCase):

    def test_fires_with_6_parameters(self):
        source = "def f(a, b, c, d, e, g): pass\n"

        detail = analyze(source)

        self.assertIn(
            "long-parameter-list",
            smell_types(detail),
        )

    def test_does_not_fire_with_5_parameters(self):
        source = "def f(a, b, c, d, e): pass\n"

        detail = analyze(source)

        self.assertNotIn(
            "long-parameter-list",
            smell_types(detail),
        )

    def test_self_is_not_counted(self):
        source = (
            "class C:\n"
            "    def m(self, a, b, c, d, e): pass\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "long-parameter-list",
            smell_types(detail),
        )

    def test_fires_when_self_plus_6_parameters(self):
        source = (
            "class C:\n"
            "    def m(self, a, b, c, d, e, g): pass\n"
        )

        detail = analyze(source)

        self.assertIn(
            "long-parameter-list",
            smell_types(detail),
        )


class DataClassTest(SimpleTestCase):

    def test_fires_with_3_class_level_fields(self):
        source = (
            "class Point:\n"
            "    x = 0\n"
            "    y = 0\n"
            "    z = 0\n"
        )

        detail = analyze(source)

        self.assertIn(
            "data-class",
            smell_types(detail),
        )

    def test_does_not_fire_with_2_fields(self):
        source = (
            "class Point:\n"
            "    x = 0\n"
            "    y = 0\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "data-class",
            smell_types(detail),
        )

    def test_does_not_fire_when_a_method_exists(self):
        source = (
            "class Point:\n"
            "    x = 0\n"
            "    y = 0\n"
            "    z = 0\n"
            "    def norm(self):\n"
            "        return self.x\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "data-class",
            smell_types(detail),
        )

    def test_fires_with_3_instance_fields_in_init(self):
        source = (
            "class User:\n"
            "    def __init__(self):\n"
            "        self.name = \"\"\n"
            "        self.email = \"\"\n"
            "        self.age = 0\n"
        )

        detail = analyze(source)

        self.assertIn(
            "data-class",
            smell_types(detail),
        )


class MagicNumberTest(SimpleTestCase):

    def test_fires_on_bare_literal(self):
        detail = analyze("def f():\n    return 42\n")

        self.assertIn(
            "magic-number",
            smell_types(detail),
        )

    def test_does_not_fire_on_common_constants(self):
        source = (
            "x = 0\n"
            "y = 1\n"
            "z = 100\n"
            "w = 1000\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "magic-number",
            smell_types(detail),
        )

    def test_does_not_fire_on_definition_default(self):
        source = "def f(n=7):\n    return n\n"

        detail = analyze(source)

        self.assertNotIn(
            "magic-number",
            smell_types(detail),
        )

    def test_does_not_fire_on_dunder_call_argument(self):
        source = (
            "class C:\n"
            "    def __init__(self):\n"
            "        super().__init__(42)\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "magic-number",
            smell_types(detail),
        )

    def test_does_not_fire_on_boolean(self):
        source = "flag = True\n"

        detail = analyze(source)

        self.assertNotIn(
            "magic-number",
            smell_types(detail),
        )


class BareExceptTest(SimpleTestCase):

    def test_fires_on_bare_except(self):
        source = (
            "try:\n"
            "    x = 1\n"
            "except:\n"
            "    x = 2\n"
        )

        detail = analyze(source)

        self.assertIn(
            "bare-except",
            smell_types(detail),
        )

    def test_does_not_fire_on_typed_except(self):
        source = (
            "try:\n"
            "    x = 1\n"
            "except ValueError:\n"
            "    x = 2\n"
        )

        detail = analyze(source)

        self.assertNotIn(
            "bare-except",
            smell_types(detail),
        )


class EmptyBlockTest(SimpleTestCase):

    def test_fires_on_pass_only_body(self):
        detail = analyze("def stub():\n    pass\n")

        self.assertIn(
            "empty-block",
            smell_types(detail),
        )

    def test_fires_on_docstring_plus_pass(self):
        detail = analyze(
            "def stub():\n"
            "    \"\"\"doc\"\"\"\n"
            "    pass\n"
        )

        self.assertIn(
            "empty-block",
            smell_types(detail),
        )

    def test_fires_on_ellipsis_body(self):
        detail = analyze("def abstract():\n    ...\n")

        self.assertIn(
            "empty-block",
            smell_types(detail),
        )

    def test_fires_on_empty_if_branch(self):
        detail = analyze("if x:\n    pass\n")

        self.assertIn(
            "empty-block",
            smell_types(detail),
        )

    def test_does_not_fire_on_docstring_plus_code(self):
        detail = analyze(
            "def f():\n"
            "    \"\"\"doc\"\"\"\n"
            "    return 1\n"
        )

        self.assertNotIn(
            "empty-block",
            smell_types(detail),
        )

    def test_does_not_fire_on_code_body(self):
        detail = analyze("if x:\n    y = 1\n")

        self.assertNotIn(
            "empty-block",
            smell_types(detail),
        )


class CodeSmellsEngineTest(SimpleTestCase):

    def test_clean_file_reports_zero(self):
        detail = analyze("print('hello')\n")

        self.assertEqual(
            detail["totals"]["smells"],
            0,
        )

        self.assertEqual(
            detail["totals"]["files"],
            1,
        )

        self.assertEqual(
            detail["totals"]["types"],
            0,
        )

        self.assertEqual(
            detail["by_type"],
            {},
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["scope"],
            "single_file",
        )

    def test_aggregation_counts_by_type(self):
        source = (
            "def long():\n"
            + "".join(
                f"    x{i} = 0\n"
                for i in range(31)
            )
            + "def magic():\n"
            "    return 42\n"
        )

        detail = analyze(source)

        self.assertEqual(
            detail["totals"]["smells"],
            2,
        )

        self.assertEqual(
            detail["by_type"],
            {
                "long-method": 1,
                "magic-number": 1,
            },
        )

        file_result = detail["files"][0]

        self.assertTrue(
            file_result["parsed"],
        )

        self.assertEqual(
            len(file_result["smells"]),
            2,
        )

    def test_unparsable_file_reports_partial(self):
        with tempfile.NamedTemporaryFile(
                suffix=".py",
                delete=False,
                mode="w",
                encoding="utf-8",
        ) as temp_file:
            temp_file.write("def broken(:\n")
            path = Path(temp_file.name)

        try:
            detail = CodeSmellsEngine().calculate_detailed(
                [path],
                scope="single_file",
            )
        finally:
            path.unlink()

        self.assertEqual(
            detail["completeness"],
            "partial",
        )

        self.assertTrue(
            detail["reason"],
        )

        self.assertFalse(
            detail["files"][0]["parsed"],
        )

        self.assertEqual(
            detail["totals"]["smells"],
            0,
        )

    def test_calculate_returns_zero_without_files(self):
        engine = CodeSmellsEngine()

        self.assertEqual(
            engine.calculate([]),
            0,
        )

    def test_thresholds_are_configurable(self):
        engine = CodeSmellsEngine(
            max_method_lines=5,
        )

        with tempfile.NamedTemporaryFile(
                suffix=".py",
                delete=False,
                mode="w",
                encoding="utf-8",
        ) as temp_file:
            temp_file.write(
                "def f():\n"
                "    a = 0\n"
                "    b = 0\n"
                "    c = 0\n"
                "    d = 0\n"
                "    e = 0\n"
                "    g = 0\n"
            )
            path = Path(temp_file.name)

        try:
            detail = engine.calculate_detailed(
                [path],
                scope="single_file",
            )
        finally:
            path.unlink()

        # 6 body lines exceed the custom max of 5.
        self.assertIn(
            "long-method",
            smell_types(detail),
        )

    def test_engine_is_registered(self):
        self.assertIn(
            "CODE_SMELLS",
            ENGINE_REGISTRY,
        )

        engine = get_engine("CODE_SMELLS")

        self.assertIsInstance(
            engine,
            CodeSmellsEngine,
        )


class CodeSmellsMetricSeedTest(TestCase):

    def test_code_smells_definition_is_seeded(self):
        definition = MetricDefinition.objects.get(
            name="CODE_SMELLS",
        )

        self.assertEqual(
            definition.display_name,
            "Code Smells",
        )

        self.assertEqual(
            definition.category,
            "Code Health",
        )

        self.assertFalse(
            definition.higher_is_better,
        )

        self.assertTrue(
            definition.supports_llm,
        )
