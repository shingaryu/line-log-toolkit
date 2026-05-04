"""Top-level privacy pipeline orchestration."""

from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

from .privacy_ai import analyze_with_ai, extract_entities_with_ai
from .privacy_io import read_text, write_entities, write_text
from .privacy_map import PseudonymMap
from .privacy_types import (
    PRIVACY_UNTIL_CHOICES,
    PrivacyPipelineResult,
    PseudonymMapMergeResult,
)


def resolve_model(value: str | None, default: str = "gpt-4o-mini") -> str:
    if value:
        return value
    return os.getenv("OPENAI_MODEL") or default


def run_privacy_pipeline(
    *,
    input_path: str | os.PathLike[str],
    out_dir: str | os.PathLike[str],
    map_path: str | os.PathLike[str],
    client: OpenAI,
    merge_map_path: str | os.PathLike[str] | None = None,
    extract_model: str | None = None,
    analysis_model: str | None = None,
    custom_instruction: str | None = None,
    extract_max_output_tokens: int = 2000,
    analysis_max_output_tokens: int = 1800,
    allow_short_entities: bool = False,
    until: str = "restore",
) -> PrivacyPipelineResult:
    if until not in PRIVACY_UNTIL_CHOICES:
        raise ValueError(f"until must be one of: {', '.join(PRIVACY_UNTIL_CHOICES)}")

    raw_text = read_text(input_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    entities = extract_entities_with_ai(
        client=client,
        model=resolve_model(extract_model),
        text=raw_text,
        max_output_tokens=extract_max_output_tokens,
        allow_short=allow_short_entities,
    )

    entity_map = PseudonymMap.load(map_path)
    merge_result = PseudonymMapMergeResult()
    if merge_map_path is not None:
        map_resolved = Path(map_path).resolve()
        merge_resolved = Path(merge_map_path).resolve()
        if map_resolved != merge_resolved:
            merge_source = PseudonymMap.load(merge_map_path)
            merge_result = entity_map.merge_from(merge_source)

    added = entity_map.add_entities(entities)
    entity_map.save(map_path)

    extracted_path = write_entities(out / "extracted_entities.json", entities)
    if until == "map":
        return PrivacyPipelineResult(
            extracted_entities_path=extracted_path,
            map_path=Path(map_path),
            pseudonymized_text_path=None,
            analysis_pseudonymized_path=None,
            analysis_restored_path=None,
            entity_count=len(entities),
            new_entity_count=added,
            reused_entry_count=merge_result.imported_count,
            merged_entry_count=merge_result.merged_count,
            merge_conflict_count=merge_result.conflict_count,
            completed_until=until,
        )

    pseudonymized_text = entity_map.pseudonymize(raw_text)
    pseudonymized_path = write_text(out / "pseudonymized.txt", pseudonymized_text)
    if until == "pseudonymize":
        return PrivacyPipelineResult(
            extracted_entities_path=extracted_path,
            map_path=Path(map_path),
            pseudonymized_text_path=pseudonymized_path,
            analysis_pseudonymized_path=None,
            analysis_restored_path=None,
            entity_count=len(entities),
            new_entity_count=added,
            reused_entry_count=merge_result.imported_count,
            merged_entry_count=merge_result.merged_count,
            merge_conflict_count=merge_result.conflict_count,
            completed_until=until,
        )

    analysis_pseudonymized = analyze_with_ai(
        client=client,
        model=resolve_model(analysis_model),
        pseudonymized_text=pseudonymized_text,
        custom_instruction=custom_instruction,
        max_output_tokens=analysis_max_output_tokens,
    )
    analysis_pseudo_path = write_text(
        out / "analysis_pseudonymized.md",
        analysis_pseudonymized,
    )
    if until == "analysis":
        return PrivacyPipelineResult(
            extracted_entities_path=extracted_path,
            map_path=Path(map_path),
            pseudonymized_text_path=pseudonymized_path,
            analysis_pseudonymized_path=analysis_pseudo_path,
            analysis_restored_path=None,
            entity_count=len(entities),
            new_entity_count=added,
            reused_entry_count=merge_result.imported_count,
            merged_entry_count=merge_result.merged_count,
            merge_conflict_count=merge_result.conflict_count,
            completed_until=until,
        )

    analysis_restored = entity_map.restore(analysis_pseudonymized)
    analysis_restored_path = write_text(out / "analysis_restored.md", analysis_restored)

    return PrivacyPipelineResult(
        extracted_entities_path=extracted_path,
        map_path=Path(map_path),
        pseudonymized_text_path=pseudonymized_path,
        analysis_pseudonymized_path=analysis_pseudo_path,
        analysis_restored_path=analysis_restored_path,
        entity_count=len(entities),
        new_entity_count=added,
        reused_entry_count=merge_result.imported_count,
        merged_entry_count=merge_result.merged_count,
        merge_conflict_count=merge_result.conflict_count,
        completed_until=until,
    )
