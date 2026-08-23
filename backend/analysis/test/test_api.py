from rest_framework.test import APITestCase

from analysis.models import MetricDefinition


# Ground-truth catalog order: the seeded definitions sorted by their
# canonical name (the viewset's stable ordering).
EXPECTED_CATALOG_NAMES = [
    "CBO",
    "CODE_SMELLS",
    "COGNITIVE",
    "CYCLIC",
    "CYCLOMATIC",
    "DIT",
    "DUPLICATION",
    "Halstead",
    "INSTABILITY",
    "LCOM",
    "LOC",
    "VIOLATIONS",
]

EXPECTED_FIELDS = [
    "name",
    "display_name",
    "category",
    "description",
    "unit",
    "higher_is_better",
    "supports_llm",
]


class MetricCatalogEndpointTest(APITestCase):
    """GET /api/metrics/ — the public catalog of seeded definitions."""

    def test_catalog_is_readable_without_authentication(self):
        response = self.client.get("/api/metrics/")
        self.assertEqual(response.status_code, 200)

    def test_catalog_returns_all_seeded_metrics_in_name_order(self):
        response = self.client.get("/api/metrics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 12)
        self.assertEqual(
            [item["name"] for item in response.data],
            EXPECTED_CATALOG_NAMES,
        )

    def test_every_entry_carries_the_full_definition(self):
        response = self.client.get("/api/metrics/")
        self.assertEqual(len(response.data), 12)

        for item in response.data:
            with self.subTest(name=item["name"]):
                self.assertEqual(
                    set(item.keys()),
                    set(EXPECTED_FIELDS),
                )

    def test_loc_entry_has_seeded_metadata(self):
        response = self.client.get("/api/metrics/")
        loc = next(
            item for item in response.data
            if item["name"] == "LOC"
        )
        self.assertEqual(loc["display_name"], "Lines of Code")
        self.assertEqual(loc["category"], "Complexity & Size")
        self.assertEqual(loc["unit"], "lines")
        self.assertTrue(loc["description"])
        self.assertFalse(loc["higher_is_better"])
        self.assertTrue(loc["supports_llm"])

    def test_single_definition_is_retrievable(self):
        loc = MetricDefinition.objects.get(name="LOC")
        response = self.client.get(f"/api/metrics/{loc.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "LOC")
        self.assertEqual(
            response.data["display_name"],
            "Lines of Code",
        )
