from django.db import migrations


def seed_duplication(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.get_or_create(
        name="DUPLICATION",
        defaults={
            "display_name": "Duplication %",
            "category": "Code Health",
            "description": (
                "Token-based duplication following SonarQube "
                "semantics: token streams from the standard-library "
                "tokenizer are compared across the analyzed files "
                "with configurable minimums (100 tokens / 10 "
                "lines); duplicated_lines is the union of physical "
                "lines in duplicated blocks and the ratio is "
                "duplicated_lines / lines_of_code x 100. Not "
                "applicable to a single-file input (see "
                "docs/duplication.md)."
            ),
            "unit": "",
            "higher_is_better": False,
            "supports_llm": True,
        },
    )


def unseed_duplication(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.filter(
        name="DUPLICATION",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0007_seed_code_smells"),
    ]

    operations = [
        migrations.RunPython(
            seed_duplication,
            unseed_duplication,
        ),
    ]
