from django.db import migrations


def seed_cyclic(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.get_or_create(
        name="CYCLIC",
        defaults={
            "display_name": "Cyclic Dependencies",
            "category": "Design Quality",
            "description": (
                "Dependency cycles in the module graph: strongly "
                "connected components of two or more modules, each "
                "reported once with its member modules. Self-loops "
                "are reported separately. Not applicable to a "
                "single-file input."
            ),
            "unit": "",
            "higher_is_better": False,
            "supports_llm": True,
        },
    )


def unseed_cyclic(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.filter(
        name="CYCLIC",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0003_seed_instability"),
    ]

    operations = [
        migrations.RunPython(
            seed_cyclic,
            unseed_cyclic,
        ),
    ]
