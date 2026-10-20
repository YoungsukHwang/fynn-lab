"""Synthetic member profiles: loading and rendering into the prompt."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from fynn import config


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    summary: str
    as_of: date
    credit: dict[str, Any]
    products: dict[str, dict[str, Any] | None]
    recent_events: list[str]


def load_personas(directory: Path = config.PERSONAS_DIR) -> dict[str, Persona]:
    personas = {}
    for path in sorted(directory.glob("*.json")):
        persona = Persona.model_validate_json(path.read_text(encoding="utf-8"))
        if persona.id != path.stem:
            raise ValueError(f"{path.name}: id {persona.id!r} must equal the file name")
        personas[persona.id] = persona
    if not personas:
        raise FileNotFoundError(f"no persona files in {directory}")
    return personas


def render_profile(persona: Persona) -> str:
    """The member context both bots receive, identical in format."""
    data = persona.model_dump(mode="json", exclude={"id"})
    # Compact JSON: about 20% fewer tokens than indented, same content.
    return (
        f"Today is {persona.as_of.isoformat()}. This is the signed-in member's profile. "
        "It is the only member data you have.\n"
        f"```json\n{json.dumps(data, separators=(',', ':'))}\n```"
    )
