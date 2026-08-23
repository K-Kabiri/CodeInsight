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


def finding(detail: dict, smell_type: str) -> dict:
    """The single finding of the given type in the analyzed file."""
    matches = [
        smell
        for smell in detail["files"][0]["smells"]
        if smell["type"] == smell_type
    ]

    assert len(matches) == 1, (
        f"expected exactly one {smell_type}, got {len(matches)}"
    )

    return matches[0]


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


class SearchableNamesTest(SimpleTestCase):

    def test_fires_on_single_letter_parameter(self):
        detail = analyze(
            "def f(n):\n"
            "    return n\n"
        )

        self.assertIn(
            "searchable-names",
            smell_types(detail),
        )

        self.assertEqual(
            finding(detail, "searchable-names")["entity"],
            "n",
        )

        self.assertEqual(
            finding(detail, "searchable-names")["entity_type"],
            "parameter",
        )

        self.assertEqual(
            finding(detail, "searchable-names")["lineno"],
            1,
        )

    def test_fires_on_single_letter_local(self):
        detail = analyze(
            "def f():\n"
            "    n = 1\n"
            "    return n\n"
        )

        self.assertIn(
            "searchable-names",
            smell_types(detail),
        )

        self.assertEqual(
            finding(detail, "searchable-names")["entity"],
            "n",
        )

        self.assertEqual(
            finding(detail, "searchable-names")["entity_type"],
            "variable",
        )

        self.assertEqual(
            finding(detail, "searchable-names")["lineno"],
            2,
        )

    def test_does_not_fire_on_loop_counter(self):
        detail = analyze(
            "def f():\n"
            "    for i in range(3):\n"
            "        print(i)\n"
        )

        self.assertNotIn(
            "searchable-names",
            smell_types(detail),
        )

    def test_does_not_fire_on_exception_name(self):
        detail = analyze(
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError as e:\n"
            "        print(e)\n"
        )

        self.assertNotIn(
            "searchable-names",
            smell_types(detail),
        )

    def test_fires_on_single_letter_handler_name(self):
        detail = analyze(
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError as a:\n"
            "        print(a)\n"
        )

        matches = [
            smell
            for smell in detail["files"][0]["smells"]
            if smell["type"] == "searchable-names"
        ]

        self.assertEqual(
            len(matches),
            1,
        )

        self.assertEqual(
            matches[0]["entity"],
            "a",
        )

        self.assertEqual(
            matches[0]["entity_type"],
            "variable",
        )

    def test_does_not_fire_on_self(self):
        detail = analyze(
            "class C:\n"
            "    def m(self):\n"
            "        pass\n"
        )

        self.assertNotIn(
            "searchable-names",
            smell_types(detail),
        )

    def test_nested_scope_names_are_not_locals_of_outer(self):
        # `n` belongs to inner's parameter list, not to outer's
        # locals — exactly one finding, for inner.
        detail = analyze(
            "def outer():\n"
            "    def inner(n):\n"
            "        return n\n"
            "    return inner\n"
        )

        matches = [
            smell
            for smell in detail["files"][0]["smells"]
            if smell["type"] == "searchable-names"
        ]

        self.assertEqual(
            len(matches),
            1,
        )

        self.assertEqual(
            matches[0]["entity"],
            "n",
        )


class CommentedOutCodeTest(SimpleTestCase):

    def test_fires_on_commented_assignment(self):
        detail = analyze(
            "# x = 42\n"
            "print(1)\n"
        )

        self.assertIn(
            "commented-out-code",
            smell_types(detail),
        )

        self.assertIsNone(
            finding(detail, "commented-out-code")["entity"],
        )

        self.assertIsNone(
            finding(detail, "commented-out-code")["entity_type"],
        )

        self.assertEqual(
            finding(detail, "commented-out-code")["lineno"],
            1,
        )

    def test_fires_on_commented_function_block(self):
        detail = analyze(
            "# def old():\n"
            "#     return 1\n"
        )

        self.assertIn(
            "commented-out-code",
            smell_types(detail),
        )

    def test_does_not_fire_on_prose(self):
        detail = analyze(
            "# hello world\n"
            "# this is a note\n"
        )

        self.assertNotIn(
            "commented-out-code",
            smell_types(detail),
        )

    def test_does_not_fire_on_url(self):
        detail = analyze(
            "# see https://example.com/x=1\n"
        )

        self.assertNotIn(
            "commented-out-code",
            smell_types(detail),
        )

    def test_does_not_fire_on_directives(self):
        detail = analyze(
            "#!python\n"
            "# -*- coding: utf-8 -*-\n"
            "# noqa: E501\n"
            "# type: ignore\n"
            "x = 1\n"
        )

        self.assertNotIn(
            "commented-out-code",
            smell_types(detail),
        )

    def test_consecutive_lines_are_one_finding(self):
        detail = analyze(
            "# a = 1\n"
            "# b = 2\n"
        )

        matches = [
            smell
            for smell in detail["files"][0]["smells"]
            if smell["type"] == "commented-out-code"
        ]

        self.assertEqual(
            len(matches),
            1,
        )

    def test_entity_is_enclosing_function(self):
        detail = analyze(
            "def f():\n"
            "    # x = 42\n"
            "    return 1\n"
        )

        self.assertEqual(
            finding(detail, "commented-out-code")["entity"],
            "f",
        )

        self.assertEqual(
            finding(detail, "commented-out-code")["entity_type"],
            "function",
        )


class DeadFunctionTest(SimpleTestCase):

    def test_fires_on_unused_function(self):
        detail = analyze(
            "def unused():\n"
            "    pass\n"
        )

        self.assertIn(
            "dead-function",
            smell_types(detail),
        )

        self.assertEqual(
            finding(detail, "dead-function")["entity"],
            "unused",
        )

        self.assertEqual(
            finding(detail, "dead-function")["entity_type"],
            "function",
        )

        self.assertIsNone(
            finding(detail, "dead-function")["class_name"],
        )

    def test_does_not_fire_on_called_function(self):
        detail = analyze(
            "def used():\n"
            "    pass\n"
            "used()\n"
        )

        self.assertNotIn(
            "dead-function",
            smell_types(detail),
        )

    def test_recursion_counts_as_usage(self):
        detail = analyze(
            "def f():\n"
            "    return f()\n"
        )

        self.assertNotIn(
            "dead-function",
            smell_types(detail),
        )

    def test_entry_point_main_is_usage(self):
        detail = analyze(
            "def main():\n"
            "    pass\n"
            "if __name__ == \"__main__\":\n"
            "    main()\n"
        )

        self.assertNotIn(
            "dead-function",
            smell_types(detail),
        )

    def test_unused_method_carries_class(self):
        detail = analyze(
            "class C:\n"
            "    def helper(self):\n"
            "        pass\n"
        )

        self.assertIn(
            "dead-function",
            smell_types(detail),
        )

        self.assertEqual(
            finding(detail, "dead-function")["entity"],
            "helper",
        )

        self.assertEqual(
            finding(detail, "dead-function")["entity_type"],
            "method",
        )

        self.assertEqual(
            finding(detail, "dead-function")["class_name"],
            "C",
        )

    def test_does_not_fire_on_method_used_via_self(self):
        detail = analyze(
            "class C:\n"
            "    def run(self):\n"
            "        self.helper()\n"
            "    def helper(self):\n"
            "        pass\n"
            "c = C()\n"
            "c.run()\n"
        )

        self.assertNotIn(
            "dead-function",
            smell_types(detail),
        )

    def test_dunder_methods_are_excluded(self):
        detail = analyze(
            "class C:\n"
            "    def __init__(self):\n"
            "        pass\n"
        )

        self.assertNotIn(
            "dead-function",
            smell_types(detail),
        )

    def test_usage_in_another_file_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.py"
            second = Path(directory) / "second.py"

            first.write_text(
                "def shared():\n"
                "    pass\n",
                encoding="utf-8",
            )

            second.write_text(
                "from first import shared\n"
                "shared()\n",
                encoding="utf-8",
            )

            detail = CodeSmellsEngine().calculate_detailed(
                [first, second],
                scope="project",
            )

        self.assertNotIn(
            "dead-function",
            detail["by_type"],
        )


class EntityFieldsTest(SimpleTestCase):

    def test_long_method_function_entity(self):
        source = (
            "def create_user():\n"
            + "".join(
                f"    x{i} = 0\n"
                for i in range(31)
            )
        )

        finding_ = finding(analyze(source), "long-method")

        self.assertEqual(finding_["entity"], "create_user")
        self.assertEqual(finding_["entity_type"], "function")
        self.assertIsNone(finding_["class_name"])

        # Existing fields are unchanged.
        self.assertEqual(finding_["type"], "long-method")
        self.assertEqual(finding_["lineno"], 1)
        self.assertEqual(finding_["endline"], 32)
        self.assertIn("31 lines", finding_["message"])

    def test_long_method_method_entity(self):
        source = (
            "class Service:\n"
            "    def create_user(self):\n"
            + "".join(
                f"        x{i} = 0\n"
                for i in range(31)
            )
        )

        finding_ = finding(analyze(source), "long-method")

        self.assertEqual(finding_["entity"], "create_user")
        self.assertEqual(finding_["entity_type"], "method")
        self.assertEqual(finding_["class_name"], "Service")

    def test_deep_nesting_entity(self):
        source = (
            "def deep():\n"
            "    if a:\n"
            "        if b:\n"
            "            if c:\n"
            "                if d:\n"
            "                    x = 1\n"
        )

        finding_ = finding(analyze(source), "deep-nesting")

        self.assertEqual(finding_["entity"], "deep")
        self.assertEqual(finding_["entity_type"], "function")

    def test_long_parameter_list_entity(self):
        source = (
            "def configure(a, b, c, d, e, g):\n"
            "    pass\n"
        )

        finding_ = finding(analyze(source), "long-parameter-list")

        self.assertEqual(finding_["entity"], "configure")
        self.assertEqual(finding_["entity_type"], "function")

    def test_large_class_entity(self):
        source = (
            "class GodClass:\n"
            + "".join(
                f"    def m{i}(self): pass\n"
                for i in range(16)
            )
        )

        finding_ = finding(analyze(source), "large-class")

        self.assertEqual(finding_["entity"], "GodClass")
        self.assertEqual(finding_["entity_type"], "class")
        self.assertIsNone(finding_["class_name"])

    def test_data_class_entity(self):
        source = (
            "class Point:\n"
            "    x = 0\n"
            "    y = 0\n"
            "    z = 0\n"
        )

        finding_ = finding(analyze(source), "data-class")

        self.assertEqual(finding_["entity"], "Point")
        self.assertEqual(finding_["entity_type"], "class")

    def test_bare_except_inside_method(self):
        source = (
            "class Service:\n"
            "    def run(self):\n"
            "        try:\n"
            "            x = 1\n"
            "        except:\n"
            "            x = 2\n"
        )

        finding_ = finding(analyze(source), "bare-except")

        self.assertEqual(finding_["entity"], "run")
        self.assertEqual(finding_["entity_type"], "method")
        self.assertEqual(finding_["class_name"], "Service")

    def test_bare_except_inside_class(self):
        source = (
            "class Config:\n"
            "    try:\n"
            "        x = 1\n"
            "    except:\n"
            "        x = 2\n"
        )

        finding_ = finding(analyze(source), "bare-except")

        self.assertEqual(finding_["entity"], "Config")
        self.assertEqual(finding_["entity_type"], "class")

    def test_bare_except_at_module_level(self):
        source = (
            "try:\n"
            "    x = 1\n"
            "except:\n"
            "    x = 2\n"
        )

        finding_ = finding(analyze(source), "bare-except")

        self.assertIsNone(finding_["entity"])
        self.assertEqual(finding_["entity_type"], "except")

    def test_empty_block_function_entity(self):
        finding_ = finding(
            analyze("def stub():\n    pass\n"),
            "empty-block",
        )

        self.assertEqual(finding_["entity"], "stub")
        self.assertEqual(finding_["entity_type"], "function")

    def test_empty_block_module_level(self):
        finding_ = finding(
            analyze("if x:\n    pass\n"),
            "empty-block",
        )

        self.assertIsNone(finding_["entity"])
        self.assertEqual(finding_["entity_type"], "block")

    def test_nested_function_is_plain_function(self):
        source = (
            "class Service:\n"
            "    def run(self):\n"
            "        def helper():\n"
            "            pass\n"
            "        return helper\n"
        )

        finding_ = finding(analyze(source), "empty-block")

        self.assertEqual(finding_["entity"], "helper")
        self.assertEqual(finding_["entity_type"], "function")
        self.assertIsNone(finding_["class_name"])

    def test_searchable_names_entity(self):
        detail = analyze(
            "def process(n):\n"
            "    return n\n"
        )

        finding_ = finding(detail, "searchable-names")

        self.assertEqual(finding_["entity"], "n")
        self.assertEqual(finding_["entity_type"], "parameter")

    def test_dead_function_entity_in_class(self):
        detail = analyze(
            "class C:\n"
            "    def helper(self):\n"
            "        pass\n"
        )

        finding_ = finding(detail, "dead-function")

        self.assertEqual(finding_["entity"], "helper")
        self.assertEqual(finding_["entity_type"], "method")
        self.assertEqual(finding_["class_name"], "C")


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
            + "def short(n):\n"
            "    return n\n"
            "long()\n"
            "short(1)\n"
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
                "searchable-names": 1,
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
