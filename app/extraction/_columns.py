"""Column-aware reading-order detection for PDF pages.

PyMuPDF's default ``page.get_text()`` emits text in the PDF's internal storage
order, which interleaves the columns of a two-column CV into unreadable soup
(e.g. ``Python | Cairo University | JavaScript | 2022-2027``). This module
detects a clean two-column layout and returns the text in human reading order:
any full-width header band first, then the left column top-to-bottom, then the
right column.

Implemented clean-room from PyMuPDF's public ``get_text("blocks")`` API. The
detection is deliberately conservative — when a layout is not confidently
two-column it returns ``None`` so the caller falls back to default extraction,
guaranteeing single-column CVs (the well-tested common case) are untouched.
"""

from __future__ import annotations

import fitz

# Tunables — kept conservative so single-column CVs never trip into column mode.
_FULLWIDTH_FRAC = 0.70   # blocks wider than this fraction of the page are "full width"
_GUTTER_MIN_FRAC = 0.04  # the empty vertical gutter must be >= this fraction of page width
_MIN_COL_BLOCKS = 3      # each column needs at least this many text blocks


def _text_blocks(page) -> list[tuple]:
    # block tuple: (x0, y0, x1, y1, text, block_no, block_type); type 0 == text.
    return [b for b in page.get_text("blocks") if b[6] == 0 and b[4] and b[4].strip()]


def read_in_columns(page) -> str | None:
    """Return reading-ordered text if *page* is a confident two-column layout.

    Returns ``None`` when the page is single-column or detection is uncertain,
    signalling the caller to fall back to the default extraction.
    """
    rect = page.rect
    page_w = rect.width
    if page_w <= 0:
        return None

    blocks = _text_blocks(page)
    if len(blocks) < 2 * _MIN_COL_BLOCKS:
        return None

    narrow = [b for b in blocks if (b[2] - b[0]) < _FULLWIDTH_FRAC * page_w]
    if len(narrow) < 2 * _MIN_COL_BLOCKS:
        return None

    # Find the widest vertical gutter: a split x where the narrow blocks divide
    # cleanly into a left group (right edge <= split) and a right group (left
    # edge >= split) with no straddlers and a wide-enough empty band between.
    best = None  # (gutter_width, split_x, left_seed, right_seed)
    for split in sorted({b[0] for b in narrow}):
        left = [b for b in narrow if b[2] <= split + 1.0]
        right = [b for b in narrow if b[0] >= split - 1.0]
        if len(left) + len(right) != len(narrow):
            continue  # a block straddles the split — not a clean gutter here
        if len(left) < _MIN_COL_BLOCKS or len(right) < _MIN_COL_BLOCKS:
            continue
        gutter = split - max(b[2] for b in left)
        if gutter < _GUTTER_MIN_FRAC * page_w:
            continue
        if best is None or gutter > best[0]:
            best = (gutter, split, left, right)

    if best is None:
        return None

    _, split, left_seed, right_seed = best
    gutter_x = (max(b[2] for b in left_seed) + split) / 2.0
    col_top = min(min(b[1] for b in left_seed), min(b[1] for b in right_seed))

    # Assign every text block to header / left / right so nothing is dropped.
    # Full-width blocks above the columns are the header band (name/contact);
    # everything else is bucketed by horizontal center relative to the gutter.
    header: list[tuple] = []
    left: list[tuple] = []
    right: list[tuple] = []
    for b in blocks:
        is_fullwidth = (b[2] - b[0]) >= _FULLWIDTH_FRAC * page_w
        if is_fullwidth and b[1] < col_top - 1.0:
            header.append(b)
        elif (b[0] + b[2]) / 2.0 < gutter_x:
            left.append(b)
        else:
            right.append(b)

    def _join(region: list[tuple]) -> str:
        ordered = sorted(region, key=lambda b: (round(b[1]), round(b[0])))
        return "\n".join(b[4].strip() for b in ordered if b[4].strip())

    return "\n".join(part for part in (_join(header), _join(left), _join(right)) if part)
