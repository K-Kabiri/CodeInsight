from django.db import migrations


# Duplication now runs on single-file inputs too (the file is
# self-compared, so repeated code inside it is reported), so the
# catalog description no longer claims it is not applicable there.
CURRENT_DESCRIPTION = (
    "Token-based duplication following SonarQube "
    "semantics: the standard-library tokenizer feeds one "
    "comparison stream: on a project input every file "
    "joins it; on a single-file input the file is "
    "compared against itself, so code repeated inside "
    "one file is reported too. Repeated sequences need "
    "at least 100 tokens spanning at least 10 physical "
    "lines; duplicated_lines is the union of physical "
    "lines in duplicated blocks and the ratio is "
    "duplicated_lines / lines_of_code x 100 (see "
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
    "docs/Duplication.md)."
)


def describe_single_file_scope(apps, schema_editor):
    MetricDefinition = apps.get_model("analysis", "MetricDefinition")
    MetricDefinition.objects.filter(name="DUPLICATION").update(
        description=CURRENT_DESCRIPTION,
    )


def restore_legacy_description(apps, schema_editor):
    MetricDefinition = apps.get_model("analysis", "MetricDefinition")
    MetricDefinition.objects.filter(name="DUPLICATION").update(
        description=LEGACY_DESCRIPTION,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0010_fix_duplication_display_name"),
    ]

    operations = [
        migrations.RunPython(
            describe_single_file_scope,
            restore_legacy_description,
        ),
    ]
