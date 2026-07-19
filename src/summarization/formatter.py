from __future__ import annotations

from common.types import SummaryResult


def render_summary_markdown(summary: SummaryResult) -> str:
    lines = ["# Executive Summary", "", summary.executive_summary, ""]

    lines.append("## Decisions")
    lines.extend(f"- {d}" for d in summary.decisions)
    lines.append("")

    lines.append("## Risks")
    lines.extend(f"- {r}" for r in summary.risks)
    lines.append("")

    lines.append("## Open Questions")
    lines.extend(f"- {q}" for q in summary.open_questions)

    return "\n".join(lines).rstrip() + "\n"


def render_actions_markdown(summary: SummaryResult) -> str:
    lines = ["# Action Items"]
    for item in summary.action_items:
        suffix_parts = []
        if item.owner:
            suffix_parts.append(f"Owner: {item.owner}")
        if item.due:
            suffix_parts.append(f"Due: {item.due}")
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        lines.append(f"- {item.description}{suffix}")

    return "\n".join(lines).rstrip() + "\n"
