"""Entity matching, deduplication, and text replacement helpers."""

from __future__ import annotations

from typing import Iterable, Mapping
import re
import unicodedata

from .privacy_types import (
    EntityCandidate,
    entity_surfaces,
    normalize_entity_type,
)


PSEUDONYM_RE = re.compile(
    r"^(?:Person|Location|Organization|Contact|Event|Entity)_[A-Z]+$"
)


def entity_match_keys(text: str, entity_type: str = "OTHER") -> set[str]:
    normalized_type = normalize_entity_type(entity_type)
    base = unicodedata.normalize("NFKC", text).strip().lower()
    base = re.sub(r"\s+", "", base)
    base = re.sub(r"[・･._\-ー〜~()（）\[\]【】「」『』\"'`]", "", base)
    keys = {f"{normalized_type}:{base}"} if base else set()

    without_suffix = base
    for suffix in ("さん", "様", "さま", "くん", "君", "ちゃん", "氏", "先生"):
        if without_suffix.endswith(suffix.lower()) and len(without_suffix) > len(suffix):
            without_suffix = without_suffix[: -len(suffix)]
            break
    if without_suffix and without_suffix != base:
        keys.add(f"{normalized_type}:{without_suffix}")

    if normalized_type == "CONTACT":
        digits = re.sub(r"\D+", "", text)
        if len(digits) >= 7:
            keys.add(f"{normalized_type}:digits:{digits}")

    return keys


def is_usable_entity_text(text: str, allow_short: bool = False) -> bool:
    if not text:
        return False
    if PSEUDONYM_RE.match(text):
        return False
    if "\n" in text or "\r" in text:
        return False
    if len(text) > 120:
        return False
    if len(text) < 2 and not allow_short:
        return False
    if re.fullmatch(r"[\d\s:./\-\(\)]+", text):
        return False
    return True


def dedupe_entities(
    entities: Iterable[EntityCandidate],
    allow_short: bool = False,
) -> list[EntityCandidate]:
    seen: dict[str, EntityCandidate] = {}
    for entity in entities:
        surfaces = tuple(
            surface
            for surface in entity_surfaces(entity)
            if is_usable_entity_text(surface, allow_short=allow_short)
        )
        if not surfaces:
            continue
        key = surfaces[0]
        entity_type = normalize_entity_type(entity.entity_type)
        if key not in seen:
            seen[key] = EntityCandidate(
                surfaces=surfaces,
                entity_type=entity_type,
            )
            continue

        existing = seen[key]
        merged_surfaces = tuple(dict.fromkeys((*entity_surfaces(existing), *surfaces)))
        if existing.entity_type == "OTHER" and entity_type != "OTHER":
            seen[key] = EntityCandidate(
                surfaces=merged_surfaces,
                entity_type=entity_type,
            )
        elif merged_surfaces != entity_surfaces(existing):
            seen[key] = EntityCandidate(
                surfaces=merged_surfaces,
                entity_type=existing.entity_type,
            )

    return sorted(
        seen.values(),
        key=lambda e: (-len(entity_surfaces(e)[0]), entity_surfaces(e)[0]),
    )


def replace_many(text: str, replacements: Mapping[str, str]) -> str:
    usable = {
        source: target
        for source, target in replacements.items()
        if source and target and source != target
    }
    if not usable:
        return text
    pattern = re.compile(
        "|".join(re.escape(key) for key in sorted(usable, key=len, reverse=True))
    )
    return pattern.sub(lambda match: usable[match.group(0)], text)
