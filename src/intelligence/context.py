"""Context loader for Harbor AI assistant.

Loads YAML context files and formats them for injection into Claude prompts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONTEXT_DIR = Path(__file__).parent.parent.parent / "config" / "context"


def _load_yaml(filename: str) -> Any:
    """Load a YAML file from the context directory."""
    filepath = CONTEXT_DIR / filename
    if not filepath.exists():
        logger.warning("Context file not found: %s", filepath)
        return None
    try:
        with open(filepath) as f:
            return yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to load context file %s: %s", filepath, exc)
        return None


def _format_role(data: dict[str, Any]) -> str:
    """Format role.yaml into prompt text."""
    if not data:
        return ""

    lines = [
        f"**Title:** {data.get('title', 'Board Chair')}",
        f"**Organization:** {data.get('organization', 'Camp Downer')}",
        "",
        "**Primary Responsibilities:**",
    ]
    for resp in data.get("responsibilities", {}).get("primary", []):
        lines.append(f"- {resp}")

    lines.append("")
    lines.append("**Delegation:**")
    for role, scope in data.get("authority", {}).get("delegate_to", {}).items():
        lines.append(f"- {role.replace('_', ' ')}: {scope}")

    return "\n".join(lines)


def _format_people(data: list[dict[str, Any]]) -> str:
    """Format people.yaml into prompt text."""
    if not data:
        return ""

    sections = {
        "board_member": [],
        "staff": [],
        "prospect": [],
        "volunteer": [],
        "community": [],
        "vendor": [],
    }

    for person in data:
        ptype = person.get("type", "other")
        name = person.get("name", "Unknown")
        role = person.get("role", "")
        context = person.get("context", "").strip()

        entry = f"- **{name}** ({role}): {context[:200]}{'...' if len(context) > 200 else ''}"

        if ptype in sections:
            sections[ptype].append(entry)

    lines = []
    if sections["board_member"]:
        lines.append("**Board Members:**")
        lines.extend(sections["board_member"][:10])
    if sections["staff"]:
        lines.append("\n**Key Staff:**")
        lines.extend(sections["staff"][:5])
    if sections["prospect"]:
        lines.append("\n**Board Prospects:**")
        lines.extend(sections["prospect"][:5])

    return "\n".join(lines)


def _format_projects(data: list[dict[str, Any]]) -> str:
    """Format projects.yaml into prompt text."""
    if not data:
        return ""

    lines = []
    high_priority = [p for p in data if p.get("priority") == "high"]
    medium_priority = [p for p in data if p.get("priority") == "medium"]

    if high_priority:
        lines.append("**High Priority:**")
        for proj in high_priority[:5]:
            name = proj.get("name", "Unknown")
            owner = proj.get("owner", "TBD")
            status = proj.get("status", "active")
            blockers = proj.get("blockers", [])
            blocker_str = f" [BLOCKED: {blockers[0]}]" if blockers else ""
            lines.append(f"- {name} (owner: {owner}, status: {status}){blocker_str}")

    if medium_priority:
        lines.append("\n**Medium Priority:**")
        for proj in medium_priority[:5]:
            name = proj.get("name", "Unknown")
            owner = proj.get("owner", "TBD")
            lines.append(f"- {name} (owner: {owner})")

    return "\n".join(lines)


def _format_priorities(data: dict[str, Any]) -> str:
    """Format priorities.yaml into prompt text."""
    if not data:
        return ""

    lines = []

    focus = data.get("current_focus", [])
    if focus:
        lines.append("**Phil's Current Focus:**")
        for item in focus[:5]:
            lines.append(f"- {item.get('item', '')} ({item.get('why', '')})")

    watching = data.get("watching", [])
    if watching:
        lines.append("\n**Watching:**")
        for item in watching[:3]:
            lines.append(f"- {item.get('item', '')}")

    return "\n".join(lines)


def _format_rhythms(data: dict[str, Any]) -> str:
    """Format rhythms.yaml into prompt text - just key meetings."""
    if not data:
        return ""

    lines = ["**Upcoming Meeting Rhythms:**"]
    meetings = data.get("meetings", [])
    for mtg in meetings[:6]:
        name = mtg.get("name", "")
        freq = mtg.get("frequency", "")
        day = mtg.get("typical_day", "")
        lines.append(f"- {name}: {freq}" + (f" ({day})" if day else ""))

    return "\n".join(lines)


def build_context_prompt() -> str:
    """Build the full context prompt from all YAML files."""
    role_data = _load_yaml("role.yaml")
    people_data = _load_yaml("people.yaml")
    projects_data = _load_yaml("projects.yaml")
    priorities_data = _load_yaml("priorities.yaml")
    rhythms_data = _load_yaml("rhythms.yaml")

    sections = []

    sections.append("# Context: Phil Batalion, Camp Downer Board Chair\n")

    role_text = _format_role(role_data)
    if role_text:
        sections.append("## Role\n" + role_text)

    priorities_text = _format_priorities(priorities_data)
    if priorities_text:
        sections.append("\n## Current Priorities\n" + priorities_text)

    projects_text = _format_projects(projects_data)
    if projects_text:
        sections.append("\n## Active Projects\n" + projects_text)

    people_text = _format_people(people_data)
    if people_text:
        sections.append("\n## Key People\n" + people_text)

    rhythms_text = _format_rhythms(rhythms_data)
    if rhythms_text:
        sections.append("\n## Meeting Schedule\n" + rhythms_text)

    return "\n".join(sections)
