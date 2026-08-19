import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from analysis.engines import ENGINE_REGISTRY, get_engine
from analysis.engines.cyclic import CyclicDependenciesEngine
from analysis.models import MetricDefinition


class CyclicDependenciesEngineTest(SimpleTestCase):

    def _create_project(
            self,
            files: dict[str, str],
    ) -> list[Path]:

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

    # Two-module cycle, reported once
    def test_two_module_cycle_reported_once(self):
        files = self._create_project(
            {
                "a.py": "import b\n",
                "b.py": "import a\n",
                "c.py": "",
            }
        )

        result = CyclicDependenciesEngine().calculate_detailed(
            files,
            scope="project",
        )

        self.assertEqual(
            result["completeness"],
            "full",
        )

        self.assertEqual(
            result["cycles"],
            [["a", "b"]],
        )

        self.assertEqual(
            result["self_loops"],
            [],
        )

        self.assertEqual(
            CyclicDependenciesEngine().calculate(
                files,
                scope="project",
            ),
            1,
        )

    # Three-module cycle with a non-cyclic dependent
    def test_three_module_cycle_with_tail(self):
        files = self._create_project(
            {
                "a.py": "import b\n",
                "b.py": "import c\n",
                "c.py": "import a\n",
                "d.py": "import a\n",
            }
        )

        result = CyclicDependenciesEngine().calculate_detailed(
            files,
            scope="project",
        )

        self.assertEqual(
            result["cycles"],
            [["a", "b", "c"]],
        )

        # d depends on the cycle but is not part of it
        for cycle in result["cycles"]:
            self.assertNotIn("d", cycle)

    # Disjoint cycles, each reported once
    def test_disjoint_cycles_each_reported_once(self):
        files = self._create_project(
            {
                "a.py": "import b\n",
                "b.py": "import a\n",
                "c.py": "import d\n",
                "d.py": "import c\n",
            }
        )

        result = CyclicDependenciesEngine().calculate_detailed(
            files,
            scope="project",
        )

        self.assertEqual(
            result["cycles"],
            [["a", "b"], ["c", "d"]],
        )

        self.assertEqual(
            CyclicDependenciesEngine().calculate(
                files,
                scope="project",
            ),
            2,
        )

    # Self-loop handled without a spurious cycle
    def test_self_loop_is_not_a_spurious_cycle(self):
        files = self._create_project(
            {
                "x.py": "import x\n",
            }
        )

        result = CyclicDependenciesEngine().calculate_detailed(
            files,
            scope="project",
        )

        self.assertEqual(
            result["cycles"],
            [],
        )

        self.assertEqual(
            result["self_loops"],
            ["x"],
        )

        self.assertEqual(
            CyclicDependenciesEngine().calculate(
                files,
                scope="project",
            ),
            0,
        )

    # Acyclic graph
    def test_no_cycles(self):
        files = self._create_project(
            {
                "a.py": "import b\n",
                "b.py": "import c\n",
                "c.py": "",
            }
        )

        result = CyclicDependenciesEngine().calculate_detailed(
            files,
            scope="project",
        )

        self.assertEqual(result["cycles"], [])
        self.assertEqual(result["self_loops"], [])

        self.assertEqual(
            CyclicDependenciesEngine().calculate(
                files,
                scope="project",
            ),
            0,
        )

    # Single-file input: not applicable
    def test_single_file_reports_not_applicable(self):
        files = self._create_project(
            {
                "single.py": "import django\n",
            }
        )

        result = CyclicDependenciesEngine().calculate_detailed(
            files,
            scope="single_file",
        )

        self.assertEqual(
            result["scope"],
            "single_file",
        )

        self.assertEqual(
            result["completeness"],
            "not_applicable",
        )

        self.assertEqual(result["cycles"], [])
        self.assertEqual(result["self_loops"], [])

        self.assertIsNone(
            CyclicDependenciesEngine().calculate(
                files,
                scope="single_file",
            ),
        )

    # Registry
    def test_registry_contains_cyclic(self):
        self.assertIn(
            "CYCLIC",
            ENGINE_REGISTRY,
        )

        engine = get_engine("CYCLIC")

        self.assertIsInstance(
            engine,
            CyclicDependenciesEngine,
        )


class CyclicMetricSeedTest(TestCase):

    def test_cyclic_definition_is_seeded(self):
        definition = MetricDefinition.objects.get(
            name="CYCLIC",
        )

        self.assertEqual(
            definition.display_name,
            "Cyclic Dependencies",
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
