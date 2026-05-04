"""Public facade for the privacy pipeline modules."""

from .privacy_ai import (
    analyze_with_ai,
    build_analysis_prompt,
    build_extraction_prompt,
    extract_entities_with_ai,
    extract_regex_entities,
    parse_extraction_response,
)
from .privacy_entities import (
    dedupe_entities,
    entity_match_keys,
    is_usable_entity_text,
    replace_many,
)
from .privacy_io import read_text, write_entities, write_text
from .privacy_map import PseudonymMap
from .privacy_pipeline import resolve_model, run_privacy_pipeline
from .privacy_types import (
    ENTITY_TYPES,
    PRIVACY_UNTIL_CHOICES,
    SCHEMA_VERSION,
    EntityCandidate,
    PrivacyPipelineResult,
    PseudonymEntry,
    PseudonymMapMergeResult,
    entry_surfaces,
    entity_surfaces,
    normalize_entity_text,
    normalize_entity_type,
    normalize_surfaces,
)

__all__ = [
    "ENTITY_TYPES",
    "PRIVACY_UNTIL_CHOICES",
    "SCHEMA_VERSION",
    "EntityCandidate",
    "PrivacyPipelineResult",
    "PseudonymEntry",
    "PseudonymMap",
    "PseudonymMapMergeResult",
    "analyze_with_ai",
    "build_analysis_prompt",
    "build_extraction_prompt",
    "dedupe_entities",
    "entity_match_keys",
    "entry_surfaces",
    "entity_surfaces",
    "extract_entities_with_ai",
    "extract_regex_entities",
    "is_usable_entity_text",
    "normalize_entity_text",
    "normalize_entity_type",
    "normalize_surfaces",
    "parse_extraction_response",
    "read_text",
    "replace_many",
    "resolve_model",
    "run_privacy_pipeline",
    "write_entities",
    "write_text",
]
