import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from analysis.engines.cbo import CBOEngine


class CBOEngineTest(SimpleTestCase):

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

    # No coupling
    def test_class_without_coupling(self):
        file = self._create_file(
            """
class User:
    pass
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["cbo"],
            0,
        )

    # Instantiation
    def test_instantiation_creates_coupling(self):
        file = self._create_file(
            """
class User:
    pass


class UserService:

    def create(self):
        user = User()
        return user
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        service = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "UserService"
        )

        self.assertEqual(
            service["cbo"],
            1,
        )

        self.assertEqual(
            service["coupled_classes"],
            ["User"],
        )

    # Multiple references count once
    def test_multiple_references_count_once(self):
        file = self._create_file(
            """
class User:
    pass


class UserService:

    def create(self):
        first = User()
        second = User()

        return User()
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        service = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "UserService"
        )

        self.assertEqual(
            service["cbo"],
            1,
        )

    # Multiple coupled classes
    def test_multiple_classes(self):
        file = self._create_file(
            """
class User:
    pass


class Repository:
    pass


class UserService:

    def create(self):
        user = User()
        repository = Repository()

        return user, repository
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        service = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "UserService"
        )

        self.assertEqual(
            service["cbo"],
            2,
        )

        self.assertEqual(
            service["coupled_classes"],
            [
                "Repository",
                "User",
            ],
        )

    # Inheritance
    def test_inheritance_creates_coupling(self):
        file = self._create_file(
            """
class User:
    pass


class Admin(User):
    pass
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        admin = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "Admin"
        )

        self.assertEqual(
            admin["cbo"],
            1,
        )

        self.assertEqual(
            admin["coupled_classes"],
            ["User"],
        )

    # Type annotation
    def test_type_annotation_creates_coupling(self):
        file = self._create_file(
            """
class User:
    pass


class UserService:

    def save(
        self,
        user: User,
    ):
        pass
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        service = next(
            item
            for item in result["files"][0]["classes"]
            if item["name"] == "UserService"
        )

        self.assertEqual(
            service["cbo"],
            1,
        )

    # Non-class names do not create coupling
    def test_non_class_names_are_ignored(self):
        file = self._create_file(
            """
class UserService:

    def save(self):
        result = calculate()
        value = 10

        return result
"""
        )

        result = CBOEngine().calculate_detailed(
            [file]
        )

        service = result["files"][0]["classes"][0]

        self.assertEqual(
            service["cbo"],
            0,
        )

    # ADR-0001: scope/completeness
    def test_detail_carries_scope_and_completeness(self):
        file = self._create_file(
            """
class User:
    pass
"""
        )

        result = CBOEngine().calculate_detailed(
            [file],
            scope="single_file",
        )

        self.assertEqual(
            result["scope"],
            "single_file",
        )

        # Only couplings to classes in the analyzed file are
        # observable, so the value is a lower bound (ADR-0001).
        self.assertEqual(
            result["completeness"],
            "partial",
        )

    def test_project_scope_is_complete(self):
        file = self._create_file(
            """
class User:
    pass
"""
        )

        result = CBOEngine().calculate_detailed(
            [file],
            scope="project",
        )

        self.assertEqual(
            result["completeness"],
            "full",
        )
