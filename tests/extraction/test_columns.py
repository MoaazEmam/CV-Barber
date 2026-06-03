"""Tests for column-aware PDF reading order (app.extraction._columns)."""

import fitz

from app.extraction._columns import read_in_columns


def _two_column_page(doc):
    page = doc.new_page(width=595, height=842)  # A4
    left_lines = ["Left Alpha", "Left Bravo", "Left Charlie", "Left Delta"]
    right_lines = ["Right One", "Right Two", "Right Three", "Right Four"]
    y = 80
    for left, right in zip(left_lines, right_lines):
        # Separate textbox insertions (and a wide x-gap) keep the columns as
        # distinct blocks; stagger y so they never share a line.
        page.insert_textbox(fitz.Rect(40, y, 200, y + 24), left, fontsize=11)
        page.insert_textbox(fitz.Rect(330, y + 25, 560, y + 49), right, fontsize=11)
        y += 60
    return page, left_lines, right_lines


def test_two_column_reading_order():
    doc = fitz.open()
    page, left_lines, right_lines = _two_column_page(doc)
    text = read_in_columns(page)
    doc.close()

    assert text is not None, "two-column layout should be detected"
    # Every left-column line must precede every right-column line in the output.
    last_left = max(text.index(line) for line in left_lines)
    first_right = min(text.index(line) for line in right_lines)
    assert last_left < first_right
    # And left lines keep their top-to-bottom order.
    assert text.index("Left Alpha") < text.index("Left Delta")


def test_single_column_returns_none():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for i in range(8):
        page.insert_textbox(fitz.Rect(50, y, 400, y + 24), f"Single column line {i}", fontsize=11)
        y += 30
    result = read_in_columns(page)
    doc.close()
    # Single-column → None signals the caller to use default extraction.
    assert result is None
