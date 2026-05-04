"""AI-facing extraction and analysis functions for the privacy pipeline."""

from __future__ import annotations

from typing import Any, Mapping
import json
import re

from openai import OpenAI

from .ai_client import call_with_retries, safe_response_text
from .privacy_entities import dedupe_entities
from .privacy_types import (
    EntityCandidate,
    normalize_entity_type,
    normalize_surfaces,
)


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\bhttps?://[^\s<>()\"']+")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?){2,4}\d{3,4}(?!\d)"
)

EXTRACTION_INSTRUCTIONS = """
You extract confidential entities for pseudonymization.
Return only valid JSON, with no prose or Markdown.
Schema:
{"entities":[{"surfaces":["exact surface text","other exact surface text for the same entity"],"type":"PERSON|LOCATION|ORGANIZATION|CONTACT|EVENT|OTHER"}]}

Extract only exact strings that appear in the input and can identify a person,
place, organization, group, school, company, account/contact, address, project,
event, case, product, or other specific proper noun.
Do not include generic nouns, dates, times, relative terms, emotions, or inferred
facts. If multiple spellings, nicknames, honorific forms, abbreviations, or
contact-format variants refer to the same entity, put them in the same surfaces
array. Use only strings that appear exactly in the input. The first surface is
not a canonical name; it is only the first observed surface form for processing.
"""

ANALYSIS_INSTRUCTIONS = """
You analyze interpersonal communication objectively and constructively.
The input is pseudonymized. Treat each pseudonym as a stable identity and keep
pseudonyms exactly as written in your answer.
Write the answer in Japanese.
"""


def _decode_first_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    decoder = json.JSONDecoder()
    for idx, char in enumerate(cleaned):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned[idx:])
            return payload
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON object or array found in AI response.")


def parse_extraction_response(text: str, allow_short: bool = False) -> list[EntityCandidate]:
    payload = _decode_first_json(text)
    if isinstance(payload, Mapping):
        items = payload.get("entities") or payload.get("items") or payload.get("data") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []

    candidates: list[EntityCandidate] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        surfaces = normalize_surfaces(item.get("surfaces"))
        if not surfaces:
            continue
        type_value = item.get("type") or item.get("entity_type") or item.get("category")
        candidates.append(
            EntityCandidate(
                surfaces=surfaces,
                entity_type=normalize_entity_type(type_value),
            )
        )
    return dedupe_entities(candidates, allow_short=allow_short)


def extract_regex_entities(text: str) -> list[EntityCandidate]:
    entities: list[EntityCandidate] = []
    for pattern in (EMAIL_RE, URL_RE, PHONE_RE):
        for match in pattern.finditer(text):
            entities.append(EntityCandidate((match.group(0),), "CONTACT"))
    return dedupe_entities(entities)


def build_extraction_prompt(text: str) -> str:
    return f"TEXT_BEGIN\n{text}\nTEXT_END"


def build_analysis_prompt(text: str, custom_instruction: str | None = None) -> str:
    extra = f"\n\nAdditional user instruction:\n{custom_instruction.strip()}" if custom_instruction else ""
    return (
        "The following communication log is pseudonymized.\n"
        "Please structure the response with these sections:\n"
        "1. Situation summary\n"
        "2. Requests and concerns by participant\n"
        "3. Points that are uncertain or need confirmation\n"
        "4. Recommended next actions\n"
        "5. Draft reply or talking points, if useful\n"
        f"{extra}\n\n"
        f"LOG_BEGIN\n{text}\nLOG_END"
    )


def extract_entities_with_ai(
    client: OpenAI,
    model: str,
    text: str,
    max_output_tokens: int = 2000,
    allow_short: bool = False,
) -> list[EntityCandidate]:
    response = call_with_retries(
        client=client,
        model=model,
        instructions=EXTRACTION_INSTRUCTIONS.strip(),
        user_prompt=build_extraction_prompt(text),
        max_output_tokens=max_output_tokens,
    )
    ai_entities = parse_extraction_response(
        safe_response_text(response),
        allow_short=allow_short,
    )
    return dedupe_entities(
        [*ai_entities, *extract_regex_entities(text)],
        allow_short=allow_short,
    )


def analyze_with_ai(
    client: OpenAI,
    model: str,
    pseudonymized_text: str,
    custom_instruction: str | None = None,
    max_output_tokens: int = 1800,
) -> str:
    response = call_with_retries(
        client=client,
        model=model,
        instructions=ANALYSIS_INSTRUCTIONS.strip(),
        user_prompt=build_analysis_prompt(pseudonymized_text, custom_instruction),
        max_output_tokens=max_output_tokens,
    )
    return safe_response_text(response)
