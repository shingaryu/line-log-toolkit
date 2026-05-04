"""File IO helpers for privacy pipeline artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

from .privacy_types import EntityCandidate, entity_surfaces


def read_text(path: str | os.PathLike[str]) -> str:
    with Path(path).open("r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str | os.PathLike[str], text: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
    return p


def write_entities(path: str | os.PathLike[str], entities: Sequence[EntityCandidate]) -> Path:
    payload = {
        "entities": [
            {
                "type": entity.entity_type,
                "surfaces": list(entity_surfaces(entity)),
            }
            for entity in sorted(
                entities,
                key=lambda e: (e.entity_type, entity_surfaces(e)[0]),
            )
        ]
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return p
