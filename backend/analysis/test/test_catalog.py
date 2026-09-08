from django.test import TestCase

from analysis.engines import ENGINE_REGISTRY
from analysis.models import MetricDefinition


# Ground-truth canonical catalog: the registry key (case-sensitive)
# and the seeded definition metadata every metric must carry.
CANONICAL_CATALOG = {
    "LOC": {
        "display_name": "Lines of Code",
        "category": "Complexity & Size",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "CYCLOMATIC": {
        "display_name": "Cyclomatic Complexity",
        "category": "Complexity & Size",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "COGNITIVE": {
        "display_name": "Cognitive Complexity",
        "category": "Complexity & Size",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "Halstead": {
        "display_name": "Halstead Metrics",
        "category": "Complexity & Size",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "CBO": {
        "display_name": "Coupling Between Object Classes",
        "category": "Design Quality",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "LCOM": {
        "display_name": "Lack of Cohesion of Methods",
        "category": "Design Quality",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "DIT": {
        "display_name": "Depth of Inheritance Tree",
        "category": "Design Quality",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "INSTABILITY": {
        "display_name": "Instability",
        "category": "Design Quality",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "CYCLIC": {
        "display_name": "Cyclic Dependencies",
        "category": "Design Quality",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "VIOLATIONS": {
        "display_name": "Rule Violations",
        "category": "Code Health",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "CODE_SMELLS": {
        "display_name": "Code Smells",
        "category": "Code Health",
        "higher_is_better": False,
        "supports_llm": True,
    },
    "DUPLICATION": {
        "display_name": "Duplication",
        "category": "Code Health",
        "higher_is_better": False,
        "supports_llm": True,
    },
}


class CatalogConsistencyTest(TestCase):

    def test_every_registered_engine_has_a_seeded_definition(self):
        seeded_names = set(
            MetricDefinition.objects.values_list(
                "name",
                flat=True,
            )
        )

        self.assertTrue(
            set(ENGINE_REGISTRY.keys()).issubset(
                seeded_names
            )
        )

    def test_every_seeded_definition_has_a_registered_engine(self):
        seeded_names = set(
            MetricDefinition.objects.values_list(
                "name",
                flat=True,
            )
        )

        self.assertTrue(
            seeded_names.issubset(
                set(ENGINE_REGISTRY.keys())
            )
        )

    def test_registry_and_catalog_match_exactly(self):
        seeded_names = set(
            MetricDefinition.objects.values_list(
                "name",
                flat=True,
            )
        )

        self.assertEqual(
            seeded_names,
            set(ENGINE_REGISTRY.keys()),
        )

    def test_canonical_definitions_are_seeded_with_expected_metadata(self):
        for name, expected in CANONICAL_CATALOG.items():
            with self.subTest(name=name):
                definition = MetricDefinition.objects.get(
                    name=name,
                )

                self.assertEqual(
                    definition.display_name,
                    expected["display_name"],
                )

                self.assertEqual(
                    definition.category,
                    expected["category"],
                )

                self.assertEqual(
                    definition.higher_is_better,
                    expected["higher_is_better"],
                )

                self.assertEqual(
                    definition.supports_llm,
                    expected["supports_llm"],
                )
