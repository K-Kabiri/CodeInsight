from django.db import migrations


def seed_violations(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.get_or_create(
        name="VIOLATIONS",
        defaults={
            "display_name": "Rule Violations",
            "category": "Code Health",
            "description": (
                "Lint and security findings over the analyzed Python "
                "files: Ruff (lint) and Bandit (security) run in "
                "machine-readable mode and their output is converted "
                "into canonical violation records (rule, severity, "
                "file, line, tool). The scalar value is the total "
                "number of findings; the detail reports total, "
                "per-rule, per-severity and per-file counts. "
                "Applicable at any scope."
            ),
            "unit": "",
            "higher_is_better": False,
            "supports_llm": True,
        },
    )


def unseed_violations(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.filter(
        name="VIOLATIONS",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0005_seed_canonical_catalog"),
    ]

    operations = [
        migrations.RunPython(
            seed_violations,
            unseed_violations,
        ),
    ]
