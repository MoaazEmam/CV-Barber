"""DOCX rendering — in-place edit of the original document.

Works on a copy of the original DOCX (kept untouched in ``MasterCVModel.raw_file``)
so the output preserves every formatting detail Word applied. Using the paragraph
-index artifact, it:

  * matches each tailored experience/project entry back to its original paragraph
    block (by heading-text similarity — titles survive bullet rewrites),
  * deletes the blocks of dropped entries,
  * rewrites bullet/summary text in place (preserving run formatting),
  * reorders the kept blocks into the tailored order.

DOCX input yields DOCX output only (no PDF conversion in this pass).
"""

from __future__ import annotations

import copy
import io
import json
from difflib import SequenceMatcher

import structlog
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

log = structlog.get_logger()


def _is_list_para(paragraph: Paragraph) -> bool:
    """True only for real list/bullet items (numbering or a List/Bullet style).

    Entry sub-lines (company/location, "Mentors:…", "Personal Initiative") are NOT
    list items, so they must not be treated as bullet slots or rewritten.
    """
    pPr = paragraph._p.pPr
    if pPr is not None and pPr.find(qn("w:numPr")) is not None:
        return True
    style = (paragraph.style.name if paragraph.style else "") or ""
    return "list" in style.lower() or "bullet" in style.lower()


# ---------------------------------------------------------------------------
# Low-level paragraph helpers (operate on the underlying <w:p> XML elements).
# ---------------------------------------------------------------------------

def _delete_paragraph(paragraph: Paragraph) -> None:
    el = paragraph._p
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    """Replace a paragraph's text while keeping the first run's formatting."""
    runs = paragraph.runs
    if runs:
        runs[0].text = text
        for run in runs[1:]:
            run._element.getparent().remove(run._element)
    else:
        paragraph.add_run(text)


def _clone_after(paragraph: Paragraph) -> Paragraph:
    """Deep-copy a paragraph and insert the copy directly after it."""
    new_el = copy.deepcopy(paragraph._p)
    paragraph._p.addnext(new_el)
    return Paragraph(new_el, paragraph._parent)


def _collapse_blank_runs(doc) -> None:
    """Collapse runs of 2+ consecutive empty paragraphs down to one. Reordering
    entry blocks leaves the blank separators that sat between the originals
    clustered together, which shows as large gaps in the output."""
    prev_blank = False
    for paragraph in list(doc.paragraphs):
        blank = not (paragraph.text or "").strip()
        if blank and prev_blank:
            _delete_paragraph(paragraph)
            continue
        prev_blank = blank


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _match_score(key: str, heading: str) -> float:
    """How well a tailored entry name matches an original heading.

    Headings carry a ``Name – Tech Stack – Date`` suffix, so a plain char-ratio
    lets a SHORT unrelated heading outscore the correct, longer one (e.g. "Fashion
    House Management System" beating "Education Operations Management System –
    Microsoft Excel …" for the key "Education Operations Management System").
    Weight TOKEN RECALL — the fraction of the key's words present in the heading —
    and reward a clean prefix, both of which are robust to that suffix.
    """
    k, h = _norm(key), _norm(heading)
    if not k or not h:
        return 0.0
    if h.startswith(k) or k.startswith(h):
        return 1.0
    ktok = set(k.split())
    recall = len(ktok & set(h.split())) / len(ktok) if ktok else 0.0
    return 0.7 * recall + 0.3 * _similar(k, h)


# ---------------------------------------------------------------------------
# Matching tailored entries -> original paragraph blocks.
# ---------------------------------------------------------------------------

def _match_items(tailored_keys: list[str], original_headings: list[str]) -> list[int | None]:
    """For each tailored entry, return the index of its best original block.

    Greedy best-similarity match; each original block is used at most once.
    Returns a list parallel to ``tailored_keys``; ``None`` means no match.
    """
    used: set[int] = set()
    result: list[int | None] = []
    for key in tailored_keys:
        best_idx, best_score = None, 0.0
        for i, heading in enumerate(original_headings):
            if i in used:
                continue
            score = _match_score(key, heading)
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx is not None and best_score >= 0.4:
            used.add(best_idx)
            result.append(best_idx)
        else:
            result.append(None)
    return result


# ---------------------------------------------------------------------------
# Section editing.
# ---------------------------------------------------------------------------

def _edit_section(
    paras: list[Paragraph],
    items: list[dict],
    tailored_keys: list[str],
    tailored_bullets: list[list[str]],
) -> None:
    """Edit one entry-list section (experience or projects) in place.

    ``items`` are the original blocks from the artifact (document order). The
    tailored_* lists are parallel and already in the desired output order.
    """
    if not items:
        return

    original_headings = [paras[it["heading"]].text for it in items]
    matches = _match_items(tailored_keys, original_headings)

    kept_original = [m for m in matches if m is not None]
    kept_set = set(kept_original)

    # 1. For each kept entry: rewrite ONLY its real bullet paragraphs with the
    #    tailored bullets (sync count via delete/clone); leave the heading and any
    #    structural sub-lines (company/location, "Mentors:…") untouched. Track every
    #    surviving paragraph of the entry, in document order, so the whole block
    #    moves together on reorder.
    item_elements: dict[int, list] = {}
    for t_idx, o_idx in enumerate(matches):
        if o_idx is None:
            continue
        item = items[o_idx]
        entry_paras = [paras[i] for i in sorted(item["paragraphs"])]
        bullet_paras = [p for p in entry_paras if _is_list_para(p)]
        new_bullets = list(tailored_bullets[t_idx])

        survivors = list(entry_paras)  # Paragraph objects, document order

        if bullet_paras:
            n = min(len(bullet_paras), len(new_bullets))
            for k in range(n):
                _set_paragraph_text(bullet_paras[k], new_bullets[k])
            # Extra original bullets -> delete.
            for extra in bullet_paras[n:]:
                _delete_paragraph(extra)
                survivors.remove(extra)
            # Extra tailored bullets -> clone the last surviving bullet (keeps the
            # list formatting) and insert right after it.
            if new_bullets[n:]:
                anchor = bullet_paras[n - 1] if n else bullet_paras[0]
                pos = survivors.index(anchor) + 1
                for b in new_bullets[n:]:
                    clone = _clone_after(anchor)
                    _set_paragraph_text(clone, b)
                    survivors.insert(pos, clone)
                    anchor, pos = clone, pos + 1
        elif new_bullets:
            # Rare: an entry with no bullet paragraph to model — append the tailored
            # bullets as plain paragraphs after the last line.
            anchor = entry_paras[-1]
            for b in new_bullets:
                clone = _clone_after(anchor)
                _set_paragraph_text(clone, b)
                survivors.append(clone)
                anchor = clone

        item_elements[o_idx] = [p._p for p in survivors]

    # 2. Delete dropped items' paragraphs (reverse order to keep indices valid).
    for o_idx, item in enumerate(items):
        if o_idx in kept_set:
            continue
        for p in sorted(item["paragraphs"], reverse=True):
            _delete_paragraph(paras[p])

    # 3. Reorder kept blocks (whole heading+sub-lines+bullets blocks) into order.
    _reorder_blocks(items, kept_original, item_elements)


def _reorder_blocks(items, kept_original, item_elements) -> None:
    """Re-arrange kept paragraph blocks into ``kept_original`` order."""
    if len(kept_original) <= 1:
        return
    # Document-order list of kept items, to find the section anchor + parent.
    doc_order = [o for o in range(len(items)) if o in set(kept_original)]
    try:
        first_el = item_elements[doc_order[0]][0]
        parent = first_el.getparent()
        anchor = first_el.getprevious()
        if parent is None:
            return
        for o_idx in doc_order:
            for el in item_elements[o_idx]:
                parent.remove(el)
        cursor = anchor
        for o_idx in kept_original:
            for el in item_elements[o_idx]:
                if cursor is None:
                    parent.insert(0, el)
                else:
                    cursor.addnext(el)
                cursor = el
    except Exception as e:  # defensive: never break the whole render on reorder
        log.warning("docx_reorder_failed", error=str(e))


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

def render(original_bytes: bytes, artifact: str | dict, tailored_cv) -> bytes:
    """Produce edited DOCX bytes from the original + artifact + tailored CV."""
    art = json.loads(artifact) if isinstance(artifact, str) else artifact
    doc = Document(io.BytesIO(original_bytes))
    paras = list(doc.paragraphs)

    # Summary: replace the first summary paragraph, drop any extras.
    summary_idxs = art.get("summary_paragraphs") or []
    if summary_idxs and getattr(tailored_cv, "tailored_summary", None):
        _set_paragraph_text(paras[summary_idxs[0]], tailored_cv.tailored_summary)
        for extra in sorted(summary_idxs[1:], reverse=True):
            _delete_paragraph(paras[extra])

    # Experience.
    exp_keys = [f"{e.title} {e.company or ''}" for e in tailored_cv.experience]
    exp_bullets = [list(e.bullets) for e in tailored_cv.experience]
    _edit_section(paras, art.get("experience") or [], exp_keys, exp_bullets)

    # Projects.
    proj_keys = [p.name for p in tailored_cv.projects]
    proj_bullets = [list(p.bullets) for p in tailored_cv.projects]
    _edit_section(paras, art.get("projects") or [], proj_keys, proj_bullets)

    _collapse_blank_runs(doc)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
