from django.conf import settings

from analysis.models import Analysis, AnalysisMetric

SYSTEM_INSTRUCTION = (
    "You are a Python code-quality analyst. Explain only what the "
    "provided evidence shows — never invent metrics, values, files, "
    "or findings, and never paraphrase numbers that were not "
    "computed. Answer in English with the single structured JSON "
    "object the user asks for."
)

JSON_RESPONSE_INSTRUCTION = """\
Return exactly one JSON object, in English, with this shape:
{
  "summary": "<2-5 sentence overall summary of the code-quality story>",
  "metric_content": {
    "<METRIC_CANONICAL_NAME>": {
      "explanation": "<plain-language explanation tied to the evidence>",
      "suggestions": ["<one concrete, actionable suggestion>"]
    }
  }
}
Rules:
- Use only the canonical metric names listed in the evidence above as keys of "metric_content".
- Base every claim only on that evidence; never add numbers, findings, files or metrics that are not listed.
- Give every listed metric an "explanation"; use "suggestions": [] when nothing concrete applies.
"""


def build_messages(analysis: Analysis) -> list[dict]:
    """
    The OpenAI-style chat payload for one Analysis: a system role
    plus the evidence prompt as the user message.
    """
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": build_prompt(analysis)},
    ]


def build_prompt(analysis: Analysis) -> str:
    """
    The evidence prompt for one completed Analysis.

    Includes every selected, completed metric's scalar facts (name,
    display name, category, value, unit, higher-is-better, and the
    scope/completeness/reason the detail carries — ADR-0001) plus a
    bounded excerpt of location-rich findings. Findings beyond the
    bound are dropped, never summarized (fixed constant
    `LLM_DETAIL_BOUND`).
    """
    metrics = list(
        analysis.metrics
        .select_related("metric")
        .filter(
            selected=True,
            status=AnalysisMetric.Status.COMPLETED,
        )
        .order_by("metric__name")
    )

    lines = [
        "Python code-quality analysis evidence — the only facts the "
        "model may rely on."
    ]

    if not metrics:
        lines.append(
            "No completed metric results are available to explain."
        )
        return "\n".join(lines)

    lines.append("")
    lines.append("Metrics:")
    lines.extend(
        f"- {_scalar_evidence(metric)}"
        for metric in metrics
    )

    bound = settings.LLM_DETAIL_BOUND
    findings = []

    for metric in metrics:
        findings.extend(_detail_findings(metric))

    if findings:
        lines.append("")
        lines.append(
            f"Location-rich findings (bounded to {bound}):"
        )

        shown = findings[:bound]

        lines.extend(
            f"- {finding}"
            for finding in shown
        )

        omitted = len(findings) - bound

        if omitted > 0:
            lines.append(
                f"[… {omitted} further finding(s) omitted — "
                f"evidence bound {bound} reached]"
            )

    lines.append("")
    lines.append(JSON_RESPONSE_INSTRUCTION)

    return "\n".join(lines)


def _scalar_evidence(metric: AnalysisMetric) -> str:
    definition = metric.metric
    detail = metric.detail or {}

    parts = [
        f"{definition.name} ({definition.display_name})",
        f"category: {definition.category}",
    ]

    if metric.value is None:
        parts.append("value: none")
    else:
        value = f"value: {metric.value}"
        if definition.unit:
            value += f" {definition.unit}"
        parts.append(value)

    parts.append(
        "higher is better"
        if definition.higher_is_better
        else "lower is better"
    )

    completeness = detail.get("completeness")

    if completeness:
        parts.append(
            f"scope: {detail.get('scope')}, "
            f"completeness: {completeness}"
        )

    reason = detail.get("reason")

    if reason:
        parts.append(f"reason: {reason}")

    return "; ".join(parts)


def _detail_findings(metric: AnalysisMetric) -> list[str]:
    """
    The location-rich finding lines this metric's persisted detail
    carries (smells, violations, cycles, duplication blocks) — the
    four shapes with real code-location evidence. Other metrics
    contribute no excerpt.
    """
    detail = metric.detail or {}
    name = metric.metric.name

    if name == "CODE_SMELLS":
        return _smell_lines(detail)

    if name == "VIOLATIONS":
        return _violation_lines(detail)

    if name == "CYCLIC":
        return _cycle_lines(detail)

    if name == "DUPLICATION":
        return _duplication_lines(detail)

    return []


def _smell_lines(detail: dict) -> list[str]:
    lines = []

    for file_result in detail.get("files", []):
        file_name = file_result.get("file")

        for smell in file_result.get("smells", []):
            target = (
                smell.get("entity")
                or smell.get("entity_type")
                or "module"
            )
            lineno = smell.get("lineno")
            endline = smell.get("endline")

            location = f"{file_name}"

            if lineno is not None:
                location += (
                    f":{lineno}-{endline}"
                    if endline is not None
                    else f":{lineno}"
                )

            lines.append(
                f"smell: {location} "
                f"[{smell.get('type')} on {target}] "
                f"{smell.get('message')}"
            )

    return lines


def _violation_lines(detail: dict) -> list[str]:
    lines = []

    for record in detail.get("violations", []):
        location = str(record.get("file"))

        if record.get("line") is not None:
            location += f":{record.get('line')}"

            if record.get("column") is not None:
                location += f":{record.get('column')}"

        text = (
            f"violation: {record.get('rule')} "
            f"({record.get('severity')}, {record.get('tool')}) "
            f"at {location}: {record.get('tool_message')}"
        )

        if record.get("snippet"):
            text += f" | snippet: {record['snippet']}"

        lines.append(text)

    return lines


def _cycle_lines(detail: dict) -> list[str]:
    lines = []

    for cycle in detail.get("cycles", []):
        lines.append(
            "cycle: " + " -> ".join(str(member) for member in cycle)
        )

    for module in detail.get("self_loops", []):
        lines.append(f"self-loop: {module}")

    return lines


def _duplication_lines(detail: dict) -> list[str]:
    lines = []

    for block in detail.get("blocks", []):
        entity = block.get("entity")
        kind = block.get("kind") or block.get("entity_type")
        class_name = block.get("class_name")
        location = (
            f"{block.get('file')}:"
            f"{block.get('start_line')}-{block.get('end_line')}"
        )

        if entity and kind:
            subject = entity

            if class_name:
                subject = f"{entity} in {class_name}"

            lines.append(
                f"duplicated {kind} {subject}: {location}"
            )
        else:
            # Older persisted details (and unattributed occurrences)
            # carry no entity/kind — fall back to the plain shape.
            lines.append(f"duplicated block: {location}")

    return lines
