"""Local pseudonym map storage, merging, pseudonymization, and restoration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Mapping, Sequence

from .privacy_entities import (
    dedupe_entities,
    entity_match_keys,
    is_usable_entity_text,
    replace_many,
)
from .privacy_types import (
    ENTITY_TYPES,
    PSEUDONYM_PREFIXES,
    SCHEMA_VERSION,
    EntityCandidate,
    PseudonymEntry,
    PseudonymMapMergeResult,
    entry_surfaces,
    entity_surfaces,
    normalize_entity_text,
    normalize_entity_type,
    normalize_surfaces,
    utc_now_iso,
)


def _alpha_suffix(index: int) -> str:
    if index < 0:
        raise ValueError("index must be non-negative")
    chars: list[str] = []
    n = index
    while True:
        n, rem = divmod(n, 26)
        chars.append(chr(ord("A") + rem))
        if n == 0:
            break
        n -= 1
    return "".join(reversed(chars))


class PseudonymMap:
    def __init__(
        self,
        entries: Mapping[str, PseudonymEntry] | None = None,
        counters: Mapping[str, int] | None = None,
    ) -> None:
        self.entries: dict[str, PseudonymEntry] = dict(entries or {})
        self.counters: dict[str, int] = {
            entity_type: int((counters or {}).get(entity_type, 0))
            for entity_type in ENTITY_TYPES
        }
        self._normalize_entries()
        self._sync_counters()

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "PseudonymMap":
        p = Path(path)
        if not p.exists():
            return cls()

        with p.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        entries: dict[str, PseudonymEntry] = {}
        raw_entries = payload.get("entries", []) if isinstance(payload, Mapping) else []

        for raw in raw_entries:
            if not isinstance(raw, Mapping):
                continue
            surfaces = normalize_surfaces(raw.get("surfaces"))
            pseudonym = normalize_entity_text(raw.get("pseudonym"))
            if not surfaces or not pseudonym:
                continue
            entity_type = normalize_entity_type(raw.get("entity_type") or raw.get("type"))
            restore_as = normalize_entity_text(raw.get("restore_as")) or surfaces[0]
            entries[surfaces[0]] = PseudonymEntry(
                surfaces=surfaces,
                pseudonym=pseudonym,
                entity_type=entity_type,
                created_at=str(raw.get("created_at") or ""),
                restore_as=restore_as,
            )

        counters = payload.get("counters", {}) if isinstance(payload, Mapping) else {}
        return cls(entries=entries, counters=counters)

    def save(self, path: str | os.PathLike[str]) -> None:
        p = Path(path)
        if p.parent and str(p.parent) != ".":
            p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "counters": {k: self.counters.get(k, 0) for k in sorted(ENTITY_TYPES)},
            "entries": [
                {
                    "pseudonym": entry.pseudonym,
                    "entity_type": entry.entity_type,
                    "surfaces": list(entry_surfaces(entry)),
                    "restore_as": entry.restore_as or entry_surfaces(entry)[0],
                    "created_at": entry.created_at,
                }
                for entry in sorted(self.entries.values(), key=lambda e: e.pseudonym)
            ],
        }
        with p.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def add_entities(self, entities: Sequence[EntityCandidate]) -> int:
        added = 0
        surface_index = self._surface_index()
        for entity in dedupe_entities(entities, allow_short=True):
            surfaces = tuple(
                surface
                for surface in entity_surfaces(entity)
                if is_usable_entity_text(surface, allow_short=True)
            )
            if not surfaces:
                continue

            existing_key = self._find_existing_entry_key(
                surfaces,
                entity.entity_type,
                surface_index,
            )
            if existing_key is not None:
                entry = self.entries[existing_key]
                merged_surfaces = tuple(dict.fromkeys((*entry_surfaces(entry), *surfaces)))
                entity_type = entry.entity_type
                if entity_type == "OTHER" and entity.entity_type != "OTHER":
                    entity_type = entity.entity_type
                self.entries[existing_key] = PseudonymEntry(
                    surfaces=merged_surfaces,
                    pseudonym=entry.pseudonym,
                    entity_type=entity_type,
                    created_at=entry.created_at,
                    restore_as=entry.restore_as or entry_surfaces(entry)[0],
                )
                surface_index = self._surface_index()
                continue

            pseudonym = self._next_pseudonym(entity.entity_type)
            self.entries[surfaces[0]] = PseudonymEntry(
                surfaces=surfaces,
                pseudonym=pseudonym,
                entity_type=entity.entity_type,
                created_at=utc_now_iso(),
                restore_as=surfaces[0],
            )
            surface_index = self._surface_index()
            added += 1
        return added

    def merge_from(self, source: "PseudonymMap") -> PseudonymMapMergeResult:
        imported = 0
        merged = 0
        conflicts = 0
        surface_index = self._surface_index()

        for source_entry in source.entries.values():
            surfaces = entry_surfaces(source_entry)
            existing_key = self._find_existing_entry_key(
                surfaces,
                source_entry.entity_type,
                surface_index,
            )

            if existing_key is not None:
                self._merge_entry_surfaces(existing_key, source_entry)
                surface_index = self._surface_index()
                merged += 1
                continue

            pseudonym = source_entry.pseudonym
            if self._pseudonym_in_use(pseudonym):
                pseudonym = self._next_pseudonym(source_entry.entity_type)
                conflicts += 1

            self.entries[surfaces[0]] = PseudonymEntry(
                surfaces=surfaces,
                pseudonym=pseudonym,
                entity_type=source_entry.entity_type,
                created_at=source_entry.created_at or utc_now_iso(),
                restore_as=source_entry.restore_as or surfaces[0],
            )
            surface_index = self._surface_index()
            imported += 1

        self._sync_counters()
        return PseudonymMapMergeResult(
            imported_count=imported,
            merged_count=merged,
            conflict_count=conflicts,
        )

    def pseudonymize(self, text: str) -> str:
        return replace_many(
            text,
            {
                surface: entry.pseudonym
                for entry in self.entries.values()
                for surface in entry_surfaces(entry)
            },
        )

    def restore(self, text: str) -> str:
        return replace_many(
            text,
            {
                entry.pseudonym: entry.restore_as or entry_surfaces(entry)[0]
                for entry in self.entries.values()
            },
        )

    def _normalize_entries(self) -> None:
        normalized: dict[str, PseudonymEntry] = {}
        for entry in self.entries.values():
            surfaces = normalize_surfaces(entry.surfaces)
            pseudonym = normalize_entity_text(entry.pseudonym)
            if not surfaces or not pseudonym:
                continue
            restore_as = normalize_entity_text(entry.restore_as) or surfaces[0]
            normalized[surfaces[0]] = PseudonymEntry(
                surfaces=surfaces,
                pseudonym=pseudonym,
                entity_type=normalize_entity_type(entry.entity_type),
                created_at=entry.created_at,
                restore_as=restore_as,
            )
        self.entries = normalized

    def _surface_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for entry_key, entry in self.entries.items():
            for surface in entry_surfaces(entry):
                index[surface] = entry_key
                for key in entity_match_keys(surface, entry.entity_type):
                    index[key] = entry_key
        return index

    def _find_existing_entry_key(
        self,
        surfaces: Sequence[str],
        entity_type: str,
        surface_index: Mapping[str, str],
    ) -> str | None:
        for surface in surfaces:
            if surface in surface_index:
                return surface_index[surface]
            for key in entity_match_keys(surface, entity_type):
                if key in surface_index:
                    return surface_index[key]
        return None

    def _merge_entry_surfaces(self, entry_key: str, source: PseudonymEntry) -> None:
        entry = self.entries[entry_key]
        merged_surfaces = tuple(dict.fromkeys((*entry_surfaces(entry), *entry_surfaces(source))))
        entity_type = entry.entity_type
        if entity_type == "OTHER" and source.entity_type != "OTHER":
            entity_type = source.entity_type
        restore_as = entry.restore_as or source.restore_as or merged_surfaces[0]
        self.entries[entry_key] = PseudonymEntry(
            surfaces=merged_surfaces,
            pseudonym=entry.pseudonym,
            entity_type=entity_type,
            created_at=entry.created_at or source.created_at,
            restore_as=restore_as,
        )

    def _pseudonym_in_use(self, pseudonym: str) -> bool:
        return any(entry.pseudonym == pseudonym for entry in self.entries.values())

    def _next_pseudonym(self, entity_type: str) -> str:
        normalized_type = normalize_entity_type(entity_type)
        prefix = PSEUDONYM_PREFIXES[normalized_type]
        used = {entry.pseudonym for entry in self.entries.values()}
        idx = self.counters.get(normalized_type, 0)
        while True:
            pseudonym = f"{prefix}_{_alpha_suffix(idx)}"
            idx += 1
            if pseudonym not in used:
                self.counters[normalized_type] = idx
                return pseudonym

    def _sync_counters(self) -> None:
        for entry in self.entries.values():
            prefix = PSEUDONYM_PREFIXES.get(entry.entity_type)
            if not prefix or not entry.pseudonym.startswith(f"{prefix}_"):
                continue
            suffix = entry.pseudonym.removeprefix(f"{prefix}_")
            if not re.fullmatch(r"[A-Z]+", suffix):
                continue
            index = 0
            for char in suffix:
                index = index * 26 + (ord(char) - ord("A") + 1)
            self.counters[entry.entity_type] = max(
                self.counters.get(entry.entity_type, 0),
                index,
            )
