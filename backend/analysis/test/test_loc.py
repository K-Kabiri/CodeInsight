from pathlib import Path

from django.test import SimpleTestCase

from analysis.engines.loc import LOCEngine


class LOCEngineTest(SimpleTestCase):

    def test_loc_ignores_blank_lines_comments_and_docstrings(self):
        test_file = Path("test_sample.py")

        test_file.write_text(
            '''# Comment

def hello():
    """This is a docstring."""
    name = "Kimia"

    # Another comment
    print(name)


hello()
''',
            encoding="utf-8",
        )

        engine = LOCEngine()

        result = engine.calculate([test_file])

        self.assertEqual(result, 4)

        test_file.unlink()