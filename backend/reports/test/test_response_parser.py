import json

from django.test import SimpleTestCase

from reports.ai_errors import AIResponseParseError
from reports.response_parser import parse_response


class ResponseParserTest(SimpleTestCase):

    def test_plain_wellformed_response_parses(self):
        text = json.dumps(
            {
                "summary": "Solid overall.",
                "metric_content": {
                    "LOC": {
                        "explanation": "The file is compact.",
                        "suggestions": ["Keep it small."],
                    },
                    "CYCLOMATIC": {
                        "explanation": "Moderate complexity.",
                        "suggestions": [
                            "  Split the branches.  ",
                            "Extract helpers.",
                        ],
                    },
                },
            }
        )

        parsed = parse_response(text)

        self.assertEqual(
            parsed["summary"],
            "Solid overall.",
        )
        self.assertEqual(
            parsed["metric_content"]["LOC"],
            {"explanation": "The file is compact.", "suggestions": ["Keep it small."]},
        )
        self.assertEqual(
            parsed["metric_content"]["CYCLOMATIC"]["suggestions"],
            ["Split the branches.", "Extract helpers."],
        )

    def test_markdown_fenced_response_parses(self):
        text = (
            "```json\n"
            + json.dumps(
                {"summary": "OK.", "metric_content": {}}
            )
            + "\n```"
        )

        parsed = parse_response(text)
        self.assertEqual(parsed["summary"], "OK.")

    def test_whitespace_padding_is_tolerated(self):
        text = "\n  " + json.dumps(
            {"summary": "  Fine.  ", "metric_content": {}}
        ) + "  \n"

        parsed = parse_response(text)
        self.assertEqual(parsed["summary"], "Fine.")

    def test_missing_metric_content_defaults_to_empty(self):
        parsed = parse_response(
            json.dumps({"summary": "Only a summary."})
        )

        self.assertEqual(
            parsed,
            {"summary": "Only a summary.", "metric_content": {}},
        )

    def test_missing_suggestions_default_to_empty_list(self):
        text = json.dumps(
            {
                "summary": "S",
                "metric_content": {
                    "LOC": {"explanation": "Compact."}
                },
            }
        )

        parsed = parse_response(text)
        self.assertEqual(
            parsed["metric_content"]["LOC"]["suggestions"],
            [],
        )

    def test_blank_suggestions_are_dropped(self):
        text = json.dumps(
            {
                "summary": "S",
                "metric_content": {
                    "LOC": {
                        "explanation": "Compact.",
                        "suggestions": ["", "   ", "Real one."],
                    }
                },
            }
        )

        parsed = parse_response(text)
        self.assertEqual(
            parsed["metric_content"]["LOC"]["suggestions"],
            ["Real one."],
        )

    def test_empty_response_raises(self):
        for empty in ("", "   ", None, 42):
            with self.assertRaises(AIResponseParseError):
                parse_response(empty)

    def test_non_json_text_raises(self):
        with self.assertRaises(AIResponseParseError):
            parse_response("sorry, I cannot produce JSON")

    def test_missing_or_wrong_summary_raises(self):
        for text in (
            json.dumps({"metric_content": {}}),
            json.dumps({"summary": "", "metric_content": {}}),
            json.dumps({"summary": 12, "metric_content": {}}),
        ):
            with self.assertRaises(AIResponseParseError):
                parse_response(text)

    def test_top_level_non_object_raises(self):
        with self.assertRaises(AIResponseParseError):
            parse_response(json.dumps([1, 2, 3]))

    def test_metric_content_not_an_object_raises(self):
        with self.assertRaises(AIResponseParseError):
            parse_response(
                json.dumps(
                    {"summary": "S", "metric_content": ["LOC"]}
                )
            )

    def test_malformed_metric_entries_raise(self):
        malformed = [
            {"LOC": "not an object"},
            {"LOC": {"suggestions": ["x"]}},
            {"LOC": {"explanation": ""}},
            {"LOC": {"explanation": "x", "suggestions": "one idea"}},
            {"LOC": {"explanation": "x", "suggestions": [1, 2]}},
        ]

        for metric_content in malformed:
            with self.assertRaises(AIResponseParseError):
                parse_response(
                    json.dumps(
                        {
                            "summary": "S",
                            "metric_content": metric_content,
                        }
                    )
                )
