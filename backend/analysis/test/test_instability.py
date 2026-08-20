import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from analysis.engines import ENGINE_REGISTRY, get_engine
from analysis.engines.instability import InstabilityEngine
from analysis.models import MetricDefinition


class InstabilityEngineTest(SimpleTestCase):

    def _create_project(
            self,
            files: dict[str, str],
    ) -> list[Path]:
        """
        Write the given {relative_path: content} files into a
        temporary directory and return the file paths.
        """
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        root = Path(temp_dir.name)
        paths = []

        for rel_path, content in files.items():
            path = root / rel_path
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            path.write_text(
                content,
                encoding="utf-8",
            )
            paths.append(path)

        return paths

    # Stable / unstable hand-computed values
    def test_stable_and_unstable_modules_hand_computed(self):
        files = self._create_project(
            {
                "a.py": "import core\n",
                "b.py": "import core\n",
                "c.py": "import core\n",
                "d.py": "import core\n",
                "core.py": "import x\n",
                "x.py": "",
            }
        )

        result = InstabilityEngine().calculate_detailed(
            files,
            scope="project",
        )

        self.assertEqual(
            result["scope"],
            "project",
        )

        self.assertEqual(
            result["completeness"],
            "full",
        )

        self.assertEqual(
            result["totals"],
            {"modules": 6, "ce": 5, "ca": 5},
        )

        self.assertAlmostEqual(
            result["average"],
            4.2 / 6,
        )

        by_module = {
            item["module"]: item
            for item in result["files"]
        }

        # core: imported by four modules, imports one module
        core = by_module["core"]

        self.assertEqual(core["ce"], 1)
        self.assertEqual(core["ca"], 4)
        self.assertAlmostEqual(core["i"], 0.2)
        self.assertEqual(core["imported_modules"], ["x"])
        self.assertEqual(
            core["dependent_modules"],
            ["a", "b", "c", "d"],
        )

        # a: depends on one module, nothing depends on it
        module_a = by_module["a"]

        self.assertEqual(module_a["ce"], 1)
        self.assertEqual(module_a["ca"], 0)
        self.assertAlmostEqual(module_a["i"], 1.0)

        # x: nothing imports it, one module imports it
        module_x = by_module["x"]

        self.assertEqual(module_x["ce"], 0)
        self.assertEqual(module_x["ca"], 1)
        self.assertEqual(module_x["i"], 0.0)

        # calculate() returns the project average
        self.assertAlmostEqual(
            InstabilityEngine().calculate(
                files,
                scope="project",
            ),
            4.2 / 6,
        )

    # Import forms and internal-only edges
    def test_import_forms_and_internal_only(self):
        files = self._create_project(
            {
                "main.py": (
                    "import pkg.mod\n"
                    "from pkg import util\n"
                    "from pkg.sub import helper\n"
                    "import external_lib\n"
                    "from stdlib import os\n"
                ),
                "pkg/__init__.py": "",
                "pkg/mod.py": "from . import util\n",
                "pkg/util.py": "from .sub import helper\n",
                "pkg/sub/__init__.py": "",
                "pkg/sub/helper.py": "",
            }
        )

        result = InstabilityEngine().calculate_detailed(
            files,
            scope="project",
        )

        by_module = {
            item["module"]: item
            for item in result["files"]
        }

        main = by_module["main"]

        self.assertEqual(main["ce"], 3)
        self.assertEqual(main["ca"], 0)
        self.assertAlmostEqual(main["i"], 1.0)
        self.assertEqual(
            main["imported_modules"],
            ["pkg.mod", "pkg.sub.helper", "pkg.util"],
        )

        pkg_mod = by_module["pkg.mod"]

        self.assertEqual(pkg_mod["ce"], 1)
        self.assertEqual(pkg_mod["ca"], 1)
        self.assertAlmostEqual(pkg_mod["i"], 0.5)
        self.assertEqual(
            pkg_mod["imported_modules"],
            ["pkg.util"],
        )
        self.assertEqual(
            pkg_mod["dependent_modules"],
            ["main"],
        )

        pkg_util = by_module["pkg.util"]

        self.assertEqual(pkg_util["ce"], 1)
        self.assertEqual(pkg_util["ca"], 2)
        self.assertAlmostEqual(pkg_util["i"], 1 / 3)

        helper = by_module["pkg.sub.helper"]

        self.assertEqual(helper["ce"], 0)
        self.assertEqual(helper["ca"], 2)
        self.assertEqual(helper["i"], 0.0)

        # External imports never appear as edges or modules
        self.assertNotIn(
            "external_lib",
            set(by_module.keys()),
        )

        self.assertNotIn(
            "stdlib",
            set(by_module.keys()),
        )

        for item in result["files"]:
            self.assertNotIn(
                "external_lib",
                item["imported_modules"],
            )
            self.assertNotIn(
                "stdlib",
                item["imported_modules"],
            )

    # Longest internal prefix fallback
    def test_unresolved_submodule_falls_back_to_internal_prefix(self):
        files = self._create_project(
            {
                "main.py": "import pkg.external\n",
                "pkg/__init__.py": "",
                "pkg/internal.py": "",
            }
        )

        result = InstabilityEngine().calculate_detailed(
            files,
            scope="project",
        )

        main = next(
            item
            for item in result["files"]
            if item["module"] == "main"
        )

        self.assertEqual(main["ce"], 1)
        self.assertEqual(
            main["imported_modules"],
            ["pkg"],
        )

    # 0/0 case
    def test_no_dependencies_reports_zero_without_division_error(self):
        files = self._create_project(
            {
                "solo.py": "",
            }
        )

        result = InstabilityEngine().calculate_detailed(
            files,
            scope="project",
        )

        solo = result["files"][0]

        self.assertEqual(solo["ce"], 0)
        self.assertEqual(solo["ca"], 0)
        self.assertEqual(solo["i"], 0.0)

        self.assertEqual(
            result["totals"],
            {"modules": 1, "ce": 0, "ca": 0},
        )

        self.assertEqual(result["average"], 0.0)

        self.assertEqual(
            InstabilityEngine().calculate(
                files,
                scope="project",
            ),
            0.0,
        )

    # Single-file partial result
    def test_single_file_reports_partial_with_visible_ce_only(self):
        files = self._create_project(
            {
                "single.py": (
                    "import django\n"
                    "from requests import get\n"
                ),
            }
        )

        result = InstabilityEngine().calculate_detailed(
            files,
            scope="single_file",
        )

        self.assertEqual(
            result["scope"],
            "single_file",
        )

        self.assertEqual(
            result["completeness"],
            "partial",
        )

        self.assertNotIn("average", result)
        self.assertNotIn("totals", result)

        entry = result["files"][0]

        self.assertEqual(entry["module"], "single")
        self.assertEqual(entry["ce"], 0)
        self.assertEqual(entry["imported_modules"], [])

        # Ca and I are not claimed on a single-file Input
        self.assertNotIn("ca", entry)
        self.assertNotIn("i", entry)

        # No claimable scalar value on single-file scope
        self.assertIsNone(
            InstabilityEngine().calculate(
                files,
                scope="single_file",
            ),
        )

    # Registry
    def test_registry_contains_instability(self):
        self.assertIn(
            "INSTABILITY",
            ENGINE_REGISTRY,
        )

        engine = get_engine("INSTABILITY")

        self.assertIsInstance(
            engine,
            InstabilityEngine,
        )


class InstabilityMetricSeedTest(TestCase):

    def test_instability_definition_is_seeded(self):
        definition = MetricDefinition.objects.get(
            name="INSTABILITY",
        )

        self.assertEqual(
            definition.display_name,
            "Instability",
        )

        self.assertEqual(
            definition.category,
            "Design Quality",
        )

        self.assertFalse(
            definition.higher_is_better,
        )

        self.assertTrue(
            definition.supports_llm,
        )
