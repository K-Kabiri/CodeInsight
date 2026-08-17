import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from analysis.engines.dit import DITEngine


class DITEngineTest(SimpleTestCase):

    def _create_file(
            self,
            source: str,
    ) -> Path:

        file = tempfile.NamedTemporaryFile(
            suffix=".py",
            delete=False,
            mode="w",
            encoding="utf-8",
        )

        file.write(source)
        file.close()

        return Path(file.name)

    # No inheritance
    def test_class_without_parent(self):

        file = self._create_file(
            """
class User:
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["dit"],
            0,
        )

        self.assertEqual(
            user["inheritance_path"],
            ["User"],
        )

    # One inheritance level
    def test_one_level_inheritance(self):

        file = self._create_file(
            """
class User:
    pass

class Admin(User):
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        admin = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "Admin"
        )

        self.assertEqual(
            admin["dit"],
            1,
        )

        self.assertEqual(
            admin["inheritance_path"],
            ["Admin", "User"],
        )

    # Multiple inheritance levels
    def test_multiple_inheritance_levels(self):

        file = self._create_file(
            """
class A:
    pass

class B(A):
    pass

class C(B):
    pass

class D(C):
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        classes = {
            item["name"]: item
            for item in result["files"][0]["classes"]
        }

        self.assertEqual(
            classes["A"]["dit"],
            0,
        )

        self.assertEqual(
            classes["B"]["dit"],
            1,
        )

        self.assertEqual(
            classes["C"]["dit"],
            2,
        )

        self.assertEqual(
            classes["D"]["dit"],
            3,
        )

        self.assertEqual(
            classes["D"]["inheritance_path"],
            ["D", "C", "B", "A"],
        )

    # Multiple inheritance
    def test_multiple_inheritance_uses_longest_path(self):

        file = self._create_file(
            """
class A:
    pass

class B(A):
    pass

class C:
    pass

class D(B, C):
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        d = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "D"
        )

        self.assertEqual(
            d["dit"],
            2,
        )

        self.assertEqual(
            d["inheritance_path"],
            ["D", "B", "A"],
        )

    # External parent
    def test_external_parent_terminates_chain(self):

        file = self._create_file(
            """
class UserView(SomeExternalView):
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        user_view = (
            result["files"][0]["classes"][0]
        )

        self.assertEqual(
            user_view["dit"],
            0,
        )

        self.assertEqual(
            user_view["bases"],
            ["SomeExternalView"],
        )

    # Multiple independent hierarchies
    def test_independent_inheritance_trees(self):

        file = self._create_file(
            """
class A:
    pass

class B(A):
    pass

class X:
    pass

class Y(X):
    pass

class Z(Y):
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        classes = {
            item["name"]: item
            for item in result["files"][0]["classes"]
        }

        self.assertEqual(
            classes["A"]["dit"],
            0,
        )

        self.assertEqual(
            classes["B"]["dit"],
            1,
        )

        self.assertEqual(
            classes["X"]["dit"],
            0,
        )

        self.assertEqual(
            classes["Y"]["dit"],
            1,
        )

        self.assertEqual(
            classes["Z"]["dit"],
            2,
        )

    # Project aggregation
    def test_project_total_and_average(self):

        file = self._create_file(
            """
class A:
    pass

class B(A):
    pass

class C(B):
    pass
"""
        )

        result = DITEngine().calculate_detailed(
            [file]
        )

        self.assertEqual(
            result["total"],
            3,
        )

        self.assertEqual(
            result["class_count"],
            3,
        )

        self.assertEqual(
            result["average"],
            1.0,
        )

        self.assertEqual(
            result["max"],
            2,
        )