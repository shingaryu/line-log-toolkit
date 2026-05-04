"""
line_log_toolkit — LINE トーク履歴の解析・整理・AI 活用ツールキット（処理層）
"""

from .parser import (
    Msg,
    load_recent_messages,
    parse_month_file,
    pick_last_incoming,
    render_context_block,
)
from .splitter import split_and_parse
from .snippets import make_snippets
from .prompt_builder import (
    build_decision_prompt,
    build_user_prompt,
    write_prompt_template,
)
from .evidence import collect_evidence_snippets
from .ai_client import call_with_retries, safe_response_text
from .privacy import (
    EntityCandidate,
    PRIVACY_UNTIL_CHOICES,
    PrivacyPipelineResult,
    PseudonymEntry,
    PseudonymMap,
    PseudonymMapMergeResult,
    analyze_with_ai,
    extract_entities_with_ai,
    parse_extraction_response,
    run_privacy_pipeline,
)

__all__ = [
    "Msg",
    "load_recent_messages",
    "parse_month_file",
    "pick_last_incoming",
    "render_context_block",
    "split_and_parse",
    "make_snippets",
    "build_decision_prompt",
    "build_user_prompt",
    "write_prompt_template",
    "collect_evidence_snippets",
    "call_with_retries",
    "safe_response_text",
    "EntityCandidate",
    "PRIVACY_UNTIL_CHOICES",
    "PrivacyPipelineResult",
    "PseudonymEntry",
    "PseudonymMap",
    "PseudonymMapMergeResult",
    "analyze_with_ai",
    "extract_entities_with_ai",
    "parse_extraction_response",
    "run_privacy_pipeline",
]
