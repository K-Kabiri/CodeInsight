import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from analysis.engines.lcom import LCOMEngine


class LCOMEngineTest(SimpleTestCase):

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

    # No methods
    def test_class_without_methods(self):
        file = self._create_file(
            """
class User:
    pass
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["lcom"],
            0,
        )

    # One method
    def test_class_with_one_method(self):
        file = self._create_file(
            """
class User:

    def get_name(self):
        return self.name
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["lcom"],
            0,
        )

    # All methods share an attribute
    def test_methods_share_attribute(self):
        file = self._create_file(
            """
class User:

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def print_name(self):
        print(self.name)
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["p"],
            0,
        )

        self.assertEqual(
            user["q"],
            3,
        )

        self.assertEqual(
            user["lcom"],
            0,
        )

    # No methods share attributes
    def test_methods_do_not_share_attributes(self):
        file = self._create_file(
            """
class User:

    def get_name(self):
        return self.name

    def get_age(self):
        return self.age

    def get_email(self):
        return self.email
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["p"],
            3,
        )

        self.assertEqual(
            user["q"],
            0,
        )

        self.assertEqual(
            user["lcom"],
            3,
        )

    # Mixed shared and non-shared attributes
    def test_mixed_method_pairs(self):
        file = self._create_file(
            """
class User:

    def first(self):
        return self.name

    def second(self):
        return self.name

    def third(self):
        return self.age

    def fourth(self):
        return self.email
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["p"],
            5,
        )

        self.assertEqual(
            user["q"],
            1,
        )

        self.assertEqual(
            user["lcom"],
            4,
        )

    # Negative result becomes zero
    def test_negative_lcom_becomes_zero(self):
        file = self._create_file(
            """
class User:

    def first(self):
        return self.name

    def second(self):
        return self.name

    def third(self):
        return self.name
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        user = result["files"][0]["classes"][0]

        self.assertEqual(
            user["p"],
            0,
        )

        self.assertEqual(
            user["q"],
            3,
        )

        self.assertEqual(
            user["lcom"],
            0,
        )

    # External objects are ignored
    def test_external_object_attributes_are_ignored(self):
        file = self._create_file(
            """
class UserService:

    def save(self, user):
        return user.name

    def delete(self, repository):
        repository.delete()
"""
        )

        result = LCOMEngine().calculate_detailed(
            [file]
        )

        service = result["files"][0]["classes"][0]

        self.assertEqual(
            service["lcom"],
            1,
        )
