from __future__ import annotations

import re

from common.types import ActionItem, SummaryResult

_HEADINGS = {
    "executive_summary": "Executive Summary",
    "decisions": "Decisions",
    "action_items": "Action Items",
    "risks": "Risks",
    "open_questions": "Open Questions",
}

_HEADING_PATTERN = re.compile(
    r"^\s*#{0,6}\s*(" + "|".join(re.escape(h) for h in _HEADINGS.values()) + r")\s*:?\s*$",
    re.IGNORECASE,
)

_BULLET_PREFIX = re.compile(r"^\s*[-*•]\s*")

_ACTION_SUFFIX = re.compile(
    r"\(\s*(?:Owner:\s*(?P<owner>[^,)]+?))?\s*(?:,\s*)?(?:Due:\s*(?P<due>[^)]+?))?\s*\)\s*$",
    re.IGNORECASE,
)


def _key_for_heading(heading_text: str) -> str:
    for key, label in _HEADINGS.items():
        if label.lower() == heading_text.lower():
            return key
    raise ValueError(f"Unrecognized heading: {heading_text}")


def _strip_bullet(line: str) -> str:
    return _BULLET_PREFIX.sub("", line).strip()


def _parse_action_item(line: str) -> ActionItem:
    text = _strip_bullet(line)
    match = _ACTION_SUFFIX.search(text)
    if not match or (match.group("owner") is None and match.group("due") is None):
        return ActionItem(description=text)

    description = text[: match.start()].strip()
    owner = match.group("owner").strip() if match.group("owner") else None
    due = match.group("due").strip() if match.group("due") else None
    return ActionItem(description=description, owner=owner, due=due)


def parse_llm_response(raw: str) -> SummaryResult:
    lines = raw.splitlines()
    sections: dict[str, list[str]] = {key: [] for key in _HEADINGS}
    current_key: str | None = None
    any_heading_found = False

    for line in lines:
        match = _HEADING_PATTERN.match(line)
        if match:
            current_key = _key_for_heading(match.group(1))
            any_heading_found = True
            continue
        if current_key is not None and line.strip():
            sections[current_key].append(line)

    if not any_heading_found:
        return SummaryResult(executive_summary=raw.strip(), raw_response=raw)

    executive_summary = "\n".join(sections["executive_summary"]).strip()
    decisions = [_strip_bullet(line) for line in sections["decisions"] if line.strip()]
    risks = [_strip_bullet(line) for line in sections["risks"] if line.strip()]
    open_questions = [_strip_bullet(line) for line in sections["open_questions"] if line.strip()]
    action_items = [_parse_action_item(line) for line in sections["action_items"] if line.strip()]

    return SummaryResult(
        executive_summary=executive_summary,
        decisions=decisions,
        action_items=action_items,
        risks=risks,
        open_questions=open_questions,
        raw_response=raw,
    )
