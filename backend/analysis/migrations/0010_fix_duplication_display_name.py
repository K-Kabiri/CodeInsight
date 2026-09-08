from django.db import migrations


CLEAN_DESCRIPTION = (
    "Token-based duplication following SonarQube "
    "semantics: token streams from the standard-library "
    "tokenizer are compared across the analyzed files "
    "with configurable minimums (100 tokens / 10 "
    "lines); duplicated_lines is the union of physical "
    "lines in duplicated blocks and the ratio is "
    "duplicated_lines / lines_of_code x 100. Not "
    "applicable to a single-file input (see "
    "docs/Duplication.md)."
)

LEGACY_DESCRIPTION = (
    "Token-based duplication following SonarQube "
    "semantics: token streams from the standard-library "
    "tokenizer are compared across the analyzed files "
    "with configurable minimums (100 tokens / 10 "
    "lines); duplicated_lines is the union of physical "
    "lines in duplicated blocks and the ratio is "
    "duplicated_lines / lines_of_code x 100. Not "
    "applicable to a single-file input (see "
    "docs/Duplication %.md)."
)


# The "%" in the Duplication display name was a typo (user review):
# the metric is called "Duplication" — the density it reports is a
# percentage, but the name itself carries no sign.
def fix_duplication_display_name(apps, schema_editor):
    MetricDefinition = apps.get_model("analysis", "MetricDefinition")
    MetricDefinition.objects.filter(name="DUPLICATION").update(
        display_name="Duplication",
        description=CLEAN_DESCRIPTION,
    )


def restore_legacy_display_name(apps, schema_editor):
    MetricDefinition = apps.get_model("analysis", "MetricDefinition")
    MetricDefinition.objects.filter(name="DUPLICATION").update(
        display_name="Duplication %",
        description=LEGACY_DESCRIPTION,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0009_analysis_ai_requested"),
    ]

    operations = [
        migrations.RunPython(
            fix_duplication_display_name,
            restore_legacy_display_name,
        ),
    ]
