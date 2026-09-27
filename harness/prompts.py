"""Render role prompts with project context from config.

Prompt files live in prompts/ and may contain two placeholders:

    {{PROJECT_NAME}}         e.g. "my-cool-app"
    {{PROJECT_DESCRIPTION}}  one or two sentences about the project

This keeps the prompts project-agnostic: the same harness can drive a loop
over any repository. Fill in the `project:` section of config.yaml.
"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def render(name: str, cfg: dict) -> str:
    """Load prompts/<name>.md and substitute project context."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    project = cfg.get("project", {}) or {}
    proj_name = str(project.get("name") or "the target project").strip()
    proj_desc = str(project.get("description") or "").strip()
    text = text.replace("{{PROJECT_NAME}}", proj_name)
    text = text.replace("{{PROJECT_DESCRIPTION}}", proj_desc)
    return text
