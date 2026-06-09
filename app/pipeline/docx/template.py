"""DOCX template artifact.

For DOCX there is no generated template — the "template" is the original document
(persisted as ``MasterCVModel.raw_file``) plus a map of which paragraph indices
belong to which section/entry. This module distils the Tier 1 ``section_map``
(whose span ids are ``"p{n}"``) into that paragraph-index artifact, which is
stored as JSON in ``template_artifact``.
"""

from __future__ import annotations

import json
import re

_PID = re.compile(r"^p(\d+)(?:\.|$)")


def _pids(span_ids) -> list[int]:
    out: list[int] = []
    for sid in span_ids or []:
        if not isinstance(sid, str):
            continue
        m = _PID.match(sid)
        if m:
            out.append(int(m.group(1)))
    return sorted(set(out))


def _entry_list(section_map: dict, key: str) -> list[dict]:
    items = []
    for item in section_map.get(key, []) or []:
        if not isinstance(item, dict):
            continue
        paragraphs = _pids(item.get("spans"))
        if not paragraphs:
            continue
        items.append({"paragraphs": paragraphs, "heading": paragraphs[0]})
    return items


def build_artifact(section_map: dict) -> str:
    """Build the JSON paragraph-index artifact from a section map."""
    artifact = {
        "format": "docx",
        "summary_paragraphs": _pids(section_map.get("summary")),
        "experience": _entry_list(section_map, "experience"),
        "projects": _entry_list(section_map, "projects"),
        "education": _entry_list(section_map, "education"),
    }
    return json.dumps(artifact, ensure_ascii=False)
