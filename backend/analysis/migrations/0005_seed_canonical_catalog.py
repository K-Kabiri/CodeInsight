from django.db import migrations


# The full canonical catalog of implemented metrics. Each entry's
# `name` matches the ENGINE_REGISTRY key exactly (case-sensitive);
# INSTABILITY and CYCLIC were seeded by earlier migrations and are
# re-listed here so this migration is the single source of truth
# for the catalog (get_or_create keeps their existing rows).
CANONICAL_CATALOG = [
    {
        "name": "LOC",
        "display_name": "Lines of Code",
        "category": "Complexity & Size",
        "description": (
            "Source lines of code per Radon's raw metric definition: "
            "physical LOC, logical LOC, comment lines, and blank "
            "lines, reported per file."
        ),
        "unit": "lines",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "CYCLOMATIC",
        "display_name": "Cyclomatic Complexity",
        "category": "Complexity & Size",
        "description": (
            "McCabe's cyclomatic complexity: the number of linearly "
            "independent paths through each function's control-flow "
            "graph, computed via Radon (each analyzed block starts "
            "with a base complexity of 1)."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "COGNITIVE",
        "display_name": "Cognitive Complexity",
        "category": "Complexity & Size",
        "description": (
            "SonarSource cognitive complexity: how hard the control "
            "flow is to understand, combining structural increments "
            "(if/elif/else, loops, except, match, conditional "
            "expressions) with nesting increments."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "Halstead",
        "display_name": "Halstead Metrics",
        "category": "Complexity & Size",
        "description": (
            "Halstead software-science metrics (volume, difficulty, "
            "effort) computed via Radon; the scalar value is the "
            "total Halstead Volume across all analyzed files."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "CBO",
        "display_name": "Coupling Between Object Classes",
        "category": "Design Quality",
        "description": (
            "Coupling Between Object Classes (Chidamber & Kemerer): "
            "the number of distinct classes to which a class is "
            "coupled, counted only for classes defined inside the "
            "analyzed project; repeated references to the same "
            "class count once."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "LCOM",
        "display_name": "Lack of Cohesion of Methods",
        "category": "Design Quality",
        "description": (
            "Lack of Cohesion of Methods (Chidamber & Kemerer, "
            "LCOM1): for each class, the number of method pairs "
            "sharing no instance attribute minus the number sharing "
            "at least one, never below zero."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "DIT",
        "display_name": "Depth of Inheritance Tree",
        "category": "Design Quality",
        "description": (
            "Depth of Inheritance Tree (Chidamber & Kemerer): the "
            "longest inheritance path from a class to the root, "
            "considering only project-local parents; unresolved "
            "external bases terminate the local chain."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "INSTABILITY",
        "display_name": "Instability",
        "category": "Design Quality",
        "description": (
            "Instability (Robert C. Martin): the ratio of efferent "
            "coupling (Ce) to total coupling (Ce + Ca) — a module's "
            "tendency to change with its dependents. Computed at "
            "file level over internal imports only; I = 0 when "
            "Ca + Ce = 0."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
    {
        "name": "CYCLIC",
        "display_name": "Cyclic Dependencies",
        "category": "Design Quality",
        "description": (
            "Dependency cycles in the module graph: strongly "
            "connected components of two or more modules, each "
            "reported once with its member modules. Self-loops are "
            "reported separately. Not applicable to a single-file "
            "input."
        ),
        "unit": "",
        "higher_is_better": False,
        "supports_llm": True,
    },
]


def seed_catalog(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    for item in CANONICAL_CATALOG:
        MetricDefinition.objects.get_or_create(
            name=item["name"],
            defaults={
                key: value
                for key, value in item.items()
                if key != "name"
            },
        )


def unseed_catalog(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.filter(
        name__in=[
            item["name"]
            for item in CANONICAL_CATALOG
        ],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0004_seed_cyclic"),
    ]

    operations = [
        migrations.RunPython(
            seed_catalog,
            unseed_catalog,
        ),
    ]
