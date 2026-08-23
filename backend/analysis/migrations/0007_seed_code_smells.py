from django.db import migrations


def seed_code_smells(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.get_or_create(
        name="CODE_SMELLS",
        defaults={
            "display_name": "Code Smells",
            "category": "Code Health",
            "description": (
                "Curated structural smells detected via the AST: "
                "Long Method (> 30 lines), Large/God Class (> 200 "
                "lines or > 15 methods), Deep Nesting (> 4), Long "
                "Parameter List (> 5), Data Class (>= 3 fields, no "
                "methods), Magic Number, Bare Except, and Empty "
                "Block — each documented against Clean Code or an "
                "official reference (see docs/Code Smells.md). The "
                "scalar value is the total number of smells; the "
                "detail reports per-smell-type and per-file counts "
                "with locations. Applicable at any scope."
            ),
            "unit": "",
            "higher_is_better": False,
            "supports_llm": True,
        },
    )


def unseed_code_smells(apps, schema_editor):
    MetricDefinition = apps.get_model(
        "analysis",
        "MetricDefinition",
    )

    MetricDefinition.objects.filter(
        name="CODE_SMELLS",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0006_seed_violations"),
    ]

    operations = [
        migrations.RunPython(
            seed_code_smells,
            unseed_code_smells,
        ),
    ]
