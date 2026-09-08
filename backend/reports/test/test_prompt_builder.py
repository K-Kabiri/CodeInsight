import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from analysis.models import Analysis, AnalysisMetric, MetricDefinition
from projects.models import Project, ProjectVersion
from reports.prompt_builder import build_messages, build_prompt


class PromptBuilderTest(TestCase):
    """
    The prompt carries exactly the persisted evidence: every completed
    metric's scalar facts plus a bounded excerpt of location-rich
    findings. Details beyond the bound are dropped, never summarized.
    """

    def setUp(self):
        self._media_root = tempfile.mkdtemp(
            prefix="codeinsight-test-media-"
        )
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_root
        )
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)
        self.addCleanup(
            shutil.rmtree,
            self._media_root,
            ignore_errors=True,
        )

        owner = User.objects.create_user(
            username="alice",
            password="pass-alice",
        )
        project = Project.objects.create(
            owner=owner,
            name="Project",
        )
        version = ProjectVersion.objects.create(
            project=project,
            version_number=1,
            source_file=SimpleUploadedFile(
                "main.py",
                b"def answer():\n    return 42\n",
            ),
        )
        self.analysis = Analysis.objects.create(
            project_version=version,
        )

    def _completed_metric(self, name, value=None, detail=None):
        definition = MetricDefinition.objects.get(name=name)

        return AnalysisMetric.objects.create(
            analysis=self.analysis,
            metric=definition,
            selected=True,
            status=AnalysisMetric.Status.COMPLETED,
            value=value,
            detail=detail,
        )

    def test_prompt_includes_scalar_facts_of_every_completed_metric(self):
        loc = MetricDefinition.objects.get(name="LOC")
        smells = MetricDefinition.objects.get(name="CODE_SMELLS")

        self._completed_metric(
            "LOC",
            value=12,
            detail={"metric": "LOC"},
        )
        self._completed_metric(
            "CODE_SMELLS",
            value=2,
            detail={
                "metric": "CODE_SMELLS",
                "scope": "project",
                "completeness": "full",
                "files": [],
            },
        )

        prompt = build_prompt(self.analysis)

        self.assertIn("LOC", prompt)
        self.assertIn(loc.display_name, prompt)
        self.assertIn(f"category: {loc.category}", prompt)
        self.assertIn("value: 12", prompt)

        preference = (
            "higher is better"
            if loc.higher_is_better
            else "lower is better"
        )
        self.assertIn(preference, prompt)

        self.assertIn("CODE_SMELLS", prompt)
        self.assertIn("value: 2", prompt)
        self.assertIn("completeness: full", prompt)

    def test_scope_completeness_and_reason_are_included(self):
        detail = {
            "metric": "CYCLIC",
            "scope": "single_file",
            "completeness": "not_applicable",
            "reason": (
                "Dependency cycles require at least two modules — "
                "not applicable to a single-file input."
            ),
        }
        self._completed_metric("CYCLIC", value=None, detail=detail)

        prompt = build_prompt(self.analysis)

        self.assertIn("value: none", prompt)
        self.assertIn("scope: single_file", prompt)
        self.assertIn("completeness: not_applicable", prompt)
        self.assertIn(
            "Dependency cycles require at least two modules",
            prompt,
        )

    def test_code_smells_excerpt_carries_location_entity_and_message(self):
        detail = {
            "metric": "CODE_SMELLS",
            "scope": "project",
            "completeness": "full",
            "files": [
                {
                    "file": "app/service.py",
                    "parsed": True,
                    "smells": [
                        {
                            "type": "Long Method",
                            "lineno": 3,
                            "endline": 40,
                            "message": (
                                "Method 'run' spans 38 lines; "
                                "consider splitting it."
                            ),
                            "entity": "run",
                            "entity_type": "method",
                            "class_name": "Service",
                        }
                    ],
                }
            ],
        }
        self._completed_metric(
            "CODE_SMELLS",
            value=1,
            detail=detail,
        )

        prompt = build_prompt(self.analysis)

        self.assertIn("app/service.py:3-40", prompt)
        self.assertIn("[Long Method on run]", prompt)
        self.assertIn("Method 'run' spans 38 lines", prompt)

    def test_violation_excerpt_carries_rule_file_line_and_snippet(self):
        detail = {
            "metric": "VIOLATIONS",
            "scope": "project",
            "completeness": "full",
            "violations": [
                {
                    "rule": "F401",
                    "severity": "error",
                    "file": "main.py",
                    "line": 2,
                    "column": 8,
                    "tool_message": "`os` imported but unused",
                    "snippet": "import os",
                    "tool": "ruff",
                }
            ],
        }
        self._completed_metric(
            "VIOLATIONS",
            value=1,
            detail=detail,
        )

        prompt = build_prompt(self.analysis)

        self.assertIn("F401", prompt)
        self.assertIn("(error, ruff)", prompt)
        self.assertIn("main.py:2:8", prompt)
        self.assertIn("`os` imported but unused", prompt)
        self.assertIn("snippet: import os", prompt)

    def test_cycle_and_duplication_excerpts_are_included(self):
        self._completed_metric(
            "CYCLIC",
            value=1,
            detail={
                "metric": "CYCLIC",
                "scope": "project",
                "completeness": "full",
                "cycles": [["pkg_a.py", "pkg_b.py"]],
                "self_loops": ["pkg_c.py"],
            },
        )
        self._completed_metric(
            "DUPLICATION",
            value=25.0,
            detail={
                "metric": "DUPLICATION",
                "scope": "project",
                "completeness": "full",
                "blocks": [
                    {
                        "file": "dup.py",
                        "start_line": 10,
                        "end_line": 12,
                    }
                ],
            },
        )

        prompt = build_prompt(self.analysis)

        self.assertIn("cycle: pkg_a.py -> pkg_b.py", prompt)
        self.assertIn("self-loop: pkg_c.py", prompt)
        self.assertIn("duplicated block: dup.py:10-12", prompt)

    def test_duplication_excerpt_names_the_repeated_entity_and_kind(self):
        self._completed_metric(
            "DUPLICATION",
            value=42.0,
            detail={
                "metric": "DUPLICATION",
                "scope": "project",
                "completeness": "full",
                "blocks": [
                    {
                        "file": "service.py",
                        "start_line": 10,
                        "end_line": 40,
                        "entity": "refresh",
                        "entity_type": "method",
                        "class_name": "UserService",
                        "kind": "method",
                    },
                    {
                        "file": "legacy.py",
                        "start_line": 4,
                        "end_line": 6,
                        "entity": None,
                        "entity_type": "module",
                        "class_name": None,
                        "kind": "statements",
                    },
                ],
            },
        )

        prompt = build_prompt(self.analysis)

        # Entity-aware lines: which method/class was repeated, where.
        self.assertIn(
            "duplicated method refresh in UserService: service.py:10-40",
            prompt,
        )

        # Module-level sequence: no named entity, so the plain shape
        # keeps the location evidence.
        self.assertIn(
            "duplicated block: legacy.py:4-6",
            prompt,
        )

    @override_settings(LLM_DETAIL_BOUND=2)
    def test_findings_beyond_the_bound_are_dropped_with_marker(self):
        self._completed_metric(
            "CODE_SMELLS",
            value=5,
            detail={
                "metric": "CODE_SMELLS",
                "scope": "project",
                "completeness": "full",
                "files": [
                    {
                        "file": "app.py",
                        "parsed": True,
                        "smells": [
                            {
                                "type": "Smell",
                                "lineno": i,
                                "endline": i,
                                "message": f"smell-{label}",
                                "entity": None,
                                "entity_type": "block",
                                "class_name": None,
                            }
                            for i, label in enumerate(
                                (
                                    "one",
                                    "two",
                                    "three",
                                    "four",
                                    "five",
                                ),
                                start=1,
                            )
                        ],
                    }
                ],
            },
        )

        prompt = build_prompt(self.analysis)

        self.assertIn("smell-one", prompt)
        self.assertIn("smell-two", prompt)
        self.assertNotIn("smell-three", prompt)
        self.assertNotIn("smell-four", prompt)
        self.assertNotIn("smell-five", prompt)
        self.assertIn("3 further finding(s) omitted", prompt)
        self.assertIn("evidence bound 2 reached", prompt)

    @override_settings(LLM_DETAIL_BOUND=100)
    def test_no_marker_when_every_finding_fits(self):
        detail = {
            "metric": "CODE_SMELLS",
            "scope": "project",
            "completeness": "full",
            "files": [
                {
                    "file": "app.py",
                    "parsed": True,
                    "smells": [
                        {
                            "type": "Smell",
                            "lineno": 1,
                            "endline": 1,
                            "message": f"smell-{label}",
                            "entity": None,
                            "entity_type": "block",
                            "class_name": None,
                        }
                        for label in ("one", "two", "three")
                    ],
                }
            ],
        }
        self._completed_metric(
            "CODE_SMELLS",
            value=3,
            detail=detail,
        )

        prompt = build_prompt(self.analysis)

        self.assertIn("smell-three", prompt)
        self.assertNotIn("omitted", prompt)

    def test_build_messages_has_system_and_user_roles(self):
        self._completed_metric(
            "LOC",
            value=12,
            detail={"metric": "LOC"},
        )

        messages = build_messages(self.analysis)

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn(
            "code-quality analyst",
            messages[0]["content"],
        )
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(
            messages[1]["content"],
            build_prompt(self.analysis),
        )
        self.assertIn('"metric_content"', messages[1]["content"])
