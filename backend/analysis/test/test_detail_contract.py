import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from analysis.engines import ENGINE_REGISTRY, get_engine
from analysis.engines.violations import build_detail


# ---------------------------------------------------------------------------
# Explainable-detail contract
#
# Every engine's finding-level records must carry location and entity
# evidence so the UI can render findings uniformly and the LLM always
# gets the exact target. The convention fields are pinned per engine
# kind (Code Smells carries the full convention; Violations carries
# its extras; the already-rich engines keep their own shapes but must
# never drop their name/location evidence). A future edit that strips
# a required field fails here — the same role `test_catalog.py` plays
# for the metric catalog.
# ---------------------------------------------------------------------------


def _per_file_records(key: str):
    return lambda detail: [
        record
        for file_result in detail["files"]
        for record in file_result[key]
    ]


# name: field carrying the entity/identifier evidence.
# line: field carrying the line-location evidence (positive int).
# required: fields that must be present (None only where the contract
#           marks them nullable).
CONTRACT = {
    "LOC": {
        "records": lambda detail: detail["files"],
        "name": "file",
        "required": ("file",),
    },
    "CYCLOMATIC": {
        "records": _per_file_records("blocks"),
        "name": "name",
        "line": "lineno",
        "required": ("name", "type", "lineno", "endline"),
    },
    "COGNITIVE": {
        "records": _per_file_records("functions"),
        "name": "name",
        "line": "lineno",
        "required": ("name", "type", "lineno", "endline"),
    },
    "Halstead": {
        # Radon's Halstead functions carry no line location — the
        # entity evidence (name) is the pinned minimum here.
        "records": _per_file_records("functions"),
        "name": "name",
        "required": ("name",),
    },
    "CBO": {
        "records": _per_file_records("classes"),
        "name": "name",
        "line": "lineno",
        "required": ("name", "lineno", "endline"),
    },
    "LCOM": {
        "records": _per_file_records("classes"),
        "name": "name",
        "line": "lineno",
        "required": ("name", "lineno", "endline"),
    },
    "DIT": {
        "records": _per_file_records("classes"),
        "name": "name",
        "line": "lineno",
        "required": ("name", "lineno", "endline"),
    },
    "INSTABILITY": {
        # File-level entries: the file/module names are the entity
        # evidence; no line location applies.
        "records": lambda detail: detail["files"],
        "name": "module",
        "required": ("file", "module"),
    },
    "CYCLIC": {
        # Cycle members are plain module-name strings (graph
        # entities, not code locations) — the record itself is the
        # entity evidence.
        "records": lambda detail: [
            member
            for cycle in detail["cycles"]
            for member in cycle
        ],
        "name": None,
        "required": (),
    },
    "DUPLICATION": {
        "records": lambda detail: detail["blocks"],
        "name": "file",
        "line": "start_line",
        "required": (
            "file",
            "start_line",
            "end_line",
            "group",
            "copies",
            "ordinal",
            "entity",
            "entity_type",
            "class_name",
            "kind",
        ),
    },
    "CODE_SMELLS": {
        # Full explainable-detail convention. entity is null where
        # no named entity applies (e.g. module-level bare except).
        "records": lambda detail: [
            smell
            for file_result in detail["files"]
            for smell in file_result["smells"]
        ],
        "name": "entity",
        "line": "lineno",
        "required": (
            "type",
            "lineno",
            "endline",
            "message",
            "entity",
            "entity_type",
            "class_name",
        ),
    },
    "VIOLATIONS": {
        "records": lambda detail: detail["violations"],
        "name": "rule",
        "line": "line",
        "required": (
            "rule",
            "severity",
            "file",
            "line",
            "column",
            "tool_message",
            "snippet",
            "tool",
        ),
        # column and snippet are None when the tool output omits
        # them; the fields themselves must still be present.
        "nullable": ("column", "snippet"),
    },
}


class DetailContractTest(SimpleTestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

        root = Path(self._temp_dir.name)

        duplicated_function = (
            "def duplicated():\n"
            "    a = compute(1, 2, 3)\n"
            "    b = compute(4, 5, 6)\n"
            "    c = compute(7, 8, 9)\n"
            "    d = (a + b) * c\n"
            "    e = a - b\n"
            "    f = b - c\n"
            "    g = a * c\n"
            "    h = d + e + f\n"
            "    i = g - h\n"
            "    j = h * 2\n"
            "    k = i + j\n"
            "    l = k // 3\n"
            "    m = l % 7\n"
            "    return m\n"
        )

        long_method = (
            "def too_long():\n"
            + "".join(
                f"    x{i} = 0\n"
                for i in range(31)
            )
        )

        files = {
            "a.py": (
                "import b\n"
                "import c\n"
                "\n"
                + long_method
                + "\n"
                + duplicated_function
                + "\n"
                "class Service:\n"
                "    def run(self):\n"
                "        return duplicated()\n"
            ),
            "b.py": (
                "import c\n"
                "\n"
                + duplicated_function
            ),
            "c.py": (
                "import a\n"
                "\n"
                "def helper():\n"
                "    return 42\n"
            ),
        }

        self.files = []

        for rel_path, content in files.items():
            path = root / rel_path
            path.write_text(content, encoding="utf-8")
            self.files.append(path)

    def _detail(self, metric_name: str) -> dict:
        engine = get_engine(metric_name)

        return engine.calculate_detailed(
            self.files,
            scope="project",
        )

    def test_code_smells_carries_full_convention(self):
        detail = self._detail("CODE_SMELLS")

        smells = CONTRACT["CODE_SMELLS"]["records"](detail)

        self.assertTrue(smells)

        for smell in smells:
            for field in CONTRACT["CODE_SMELLS"]["required"]:
                self.assertIn(
                    field,
                    smell,
                    f"CODE_SMELLS record missing {field!r}",
                )

            self.assertIsInstance(smell["lineno"], int)
            self.assertGreater(smell["lineno"], 0)

            self.assertIsInstance(smell["endline"], int)
            self.assertGreaterEqual(
                smell["endline"],
                smell["lineno"],
            )

            self.assertTrue(smell["message"])

            if smell["entity"] is not None:
                self.assertTrue(str(smell["entity"]))

            self.assertIn(
                smell["entity_type"],
                (
                    "function",
                    "method",
                    "class",
                    "variable",
                    "parameter",
                    "except",
                    "block",
                ),
            )

            if smell["entity_type"] in ("method",):
                self.assertTrue(smell["class_name"])
            else:
                self.assertIn(
                    smell["class_name"],
                    (None,),
                )

    def test_every_engine_record_keeps_its_contract(self):
        for metric_name, contract in CONTRACT.items():
            if metric_name == "CODE_SMELLS":
                continue

            if metric_name == "VIOLATIONS":
                detail = build_detail(
                    "project",
                    [
                        {
                            "rule": "F401",
                            "severity": "error",
                            "file": str(self.files[0]),
                            "line": 1,
                            "column": 8,
                            "tool_message": "`os` imported but unused",
                            "snippet": "import b",
                            "tool": "ruff",
                        },
                    ],
                )
            else:
                detail = self._detail(metric_name)

            records = contract["records"](detail)

            self.assertTrue(
                records,
                f"{metric_name} produced no finding records over "
                "the fixture project — the contract is vacuous",
            )

            for record in records:
                for field in contract["required"]:
                    self.assertIn(
                        field,
                        record,
                        f"{metric_name} record missing {field!r}",
                    )

                name_key = contract.get("name")

                if name_key is None:
                    # The record itself is the entity (e.g. a cycle
                    # member module name).
                    self.assertTrue(
                        record,
                        f"{metric_name} produced an empty entity",
                    )
                elif name_key in record:
                    self.assertTrue(
                        record[name_key],
                        f"{metric_name} record has empty "
                        f"{name_key!r}",
                    )

                if "line" in contract:
                    self.assertIsInstance(
                        record[contract["line"]],
                        int,
                    )
                    self.assertGreater(
                        record[contract["line"]],
                        0,
                    )

                for field in contract.get("nullable", ()):
                    self.assertIn(
                        field,
                        record,
                        f"{metric_name} record missing {field!r}",
                    )

    def test_duplication_blocks_carry_entity_kind_and_group_evidence(self):
        # The fixture duplicates one whole function (`duplicated`)
        # across two files. Every block must say *what* was repeated
        # (the function, with its kind) and *where* (file + lines),
        # and the two copies of the same clone group must be tied
        # together by group/ordinal/copies.
        detail = self._detail("DUPLICATION")

        blocks = CONTRACT["DUPLICATION"]["records"](detail)

        self.assertEqual(
            len(blocks),
            2,
        )

        for block in blocks:
            self.assertIn(
                block["entity_type"],
                (
                    "function",
                    "method",
                    "class",
                    "module",
                    None,
                ),
            )

            if block["entity_type"] in (
                    "function",
                    "method",
                    "class",
            ):
                self.assertTrue(block["entity"])
                self.assertTrue(block["kind"])
            else:
                self.assertIsNone(block["entity"])

            self.assertIsInstance(
                block["group"],
                int,
            )
            self.assertGreaterEqual(
                block["group"],
                0,
            )
            self.assertIsInstance(
                block["copies"],
                int,
            )
            self.assertGreaterEqual(
                block["copies"],
                2,
            )
            self.assertIsInstance(
                block["ordinal"],
                int,
            )
            self.assertGreaterEqual(
                block["ordinal"],
                1,
            )
            self.assertLessEqual(
                block["ordinal"],
                block["copies"],
            )

            self.assertEqual(
                block["entity"],
                "duplicated",
            )
            self.assertEqual(
                block["entity_type"],
                "function",
            )
            self.assertEqual(
                block["kind"],
                "function",
            )
            self.assertIsNone(
                block["class_name"],
            )

        self.assertEqual(
            {block["group"] for block in blocks},
            {0},
        )
        self.assertEqual(
            {block["copies"] for block in blocks},
            {2},
        )
        self.assertEqual(
            {block["ordinal"] for block in blocks},
            {1, 2},
        )

    def test_cyclic_cycle_members_are_named_entities(self):
        detail = self._detail("CYCLIC")

        self.assertTrue(
            detail["cycles"],
            "the fixture project must contain a dependency cycle",
        )

        for cycle in detail["cycles"]:
            self.assertTrue(cycle)

            for member in cycle:
                self.assertTrue(
                    member,
                    "a cycle member must be a non-empty module name",
                )

        for member in detail["self_loops"]:
            self.assertTrue(member)


class DetailContractRegistryTest(SimpleTestCase):

    def test_contract_covers_every_registered_engine(self):
        # A new engine without a contract entry fails here, forcing
        # the convention to be pinned explicitly.
        self.assertEqual(
            set(CONTRACT.keys()),
            set(ENGINE_REGISTRY.keys()),
        )
