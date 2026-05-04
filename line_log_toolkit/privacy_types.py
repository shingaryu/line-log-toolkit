"""Shared types and normalization helpers for the privacy pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
import re


SCHEMA_VERSION = 3

ENTITY_TYPES = {
    "PERSON",
    "LOCATION",
    "ORGANIZATION",
    "CONTACT",
    "EVENT",
    "OTHER",
}

TYPE_ALIASES = {
    "PEOPLE": "PERSON",
    "PERSON_NAME": "PERSON",
    "NAME": "PERSON",
    "PLACE": "LOCATION",
    "GPE": "LOCATION",
    "ADDRESS": "LOCATION",
    "LOC": "LOCATION",
    "ORG": "ORGANIZATION",
    "COMPANY": "ORGANIZATION",
    "SCHOOL": "ORGANIZATION",
    "GROUP": "ORGANIZATION",
    "EMAIL": "CONTACT",
    "PHONE": "CONTACT",
    "URL": "CONTACT",
    "ACCOUNT": "CONTACT",
    "HANDLE": "CONTACT",
    "PROJECT": "EVENT",
    "CASE": "EVENT",
}

PSEUDONYM_PREFIXES = {
    "PERSON": "Person",
    "LOCATION": "Location",
    "ORGANIZATION": "Organization",
    "CONTACT": "Contact",
    "EVENT": "Event",
    "OTHER": "Entity",
}

PRIVACY_UNTIL_CHOICES = ("map", "pseudonymize", "analysis", "restore")


@dataclass(frozen=True)
class EntityCandidate:
    surfaces: tuple[str, ...]
    entity_type: str = "OTHER"


@dataclass(frozen=True)
class PseudonymEntry:
    surfaces: tuple[str, ...]
    pseudonym: str
    entity_type: str
    created_at: str
    restore_as: str = ""


@dataclass(frozen=True)
class PrivacyPipelineResult:
    extracted_entities_path: Path
    map_path: Path
    pseudonymized_text_path: Path | None
    analysis_pseudonymized_path: Path | None
    analysis_restored_path: Path | None
    entity_count: int
    new_entity_count: int
    reused_entry_count: int
    merged_entry_count: int
    merge_conflict_count: int
    completed_until: str


@dataclass(frozen=True)
class PseudonymMapMergeResult:
    imported_count: int = 0
    merged_count: int = 0
    conflict_count: int = 0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_entity_type(value: str | None) -> str:
    if not value:
        return "OTHER"
    key = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip().upper()).strip("_")
    key = TYPE_ALIASES.get(key, key)
    return key if key in ENTITY_TYPES else "OTHER"


def normalize_entity_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().strip("\"'`")
    text = re.sub(r"[ \t\r\n]+", " ", text).strip()
    return text


def normalize_surfaces(values: Any) -> tuple[str, ...]:
    if values is None:
        raw_values: list[Any] = []
    elif isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, Sequence):
        raw_values = list(values)
    else:
        raw_values = []

    surfaces: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        text = normalize_entity_text(value)
        if not text or text in seen:
            continue
        surfaces.append(text)
        seen.add(text)
    return tuple(surfaces)


def entity_surfaces(entity: EntityCandidate) -> tuple[str, ...]:
    return normalize_surfaces(entity.surfaces)


def entry_surfaces(entry: PseudonymEntry) -> tuple[str, ...]:
    return normalize_surfaces(entry.surfaces)
