from django.db import migrations


def seed_instability(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.get_or_create(
        name="INSTABILITY",
        defaults={
            "display_name": "Instability",
            "category": "Design Quality",
            "description": (
                "Instability (Robert C. Martin): the ratio of "
                "efferent coupling (Ce) to total coupling (Ce + Ca) "
                "— a module's tendency to change with its "
                "dependents. Computed at file level over internal "
                "imports only; I = 0 when Ca + Ce = 0."
            ),
            "unit": "",
            "higher_is_better": False,
            "supports_llm": True,
        },
    )


def unseed_instability(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.filter(
        name="INSTABILITY",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0002_analysismetric_detail"),
    ]

    operations = [
        migrations.RunPython(
            seed_instability,
            unseed_instability,
        ),
    ]
