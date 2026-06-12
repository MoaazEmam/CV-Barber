"""ODT (OpenDocument Text) extraction — stdlib only.

An .odt file is a ZIP archive whose document body lives in ``content.xml``
(ODF, ISO 26300). We walk paragraphs/headings in document order via
``itertext()`` so tables and lists read naturally, and collect hyperlink
targets into a trailing ``Links:`` line to match the PDF/DOCX extractors.
"""

import zipfile
import xml.etree.ElementTree as ET

TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
XLINK_NS = "http://www.w3.org/1999/xlink"

_PARAGRAPH_TAGS = {f"{{{TEXT_NS}}}p", f"{{{TEXT_NS}}}h"}
_LINK_TAG = f"{{{TEXT_NS}}}a"
_HREF_ATTR = f"{{{XLINK_NS}}}href"


class OdtExtractor:
    def extract_text(self, path: str) -> str:
        with zipfile.ZipFile(path) as zf:
            root = ET.fromstring(zf.read("content.xml"))

        lines: list[str] = []
        links: list[str] = []
        for elem in root.iter():
            if elem.tag in _PARAGRAPH_TAGS:
                text = " ".join("".join(elem.itertext()).split())
                if text:
                    lines.append(text)
            elif elem.tag == _LINK_TAG:
                uri = elem.get(_HREF_ATTR)
                if uri and not uri.startswith("mailto:") and uri not in links:
                    links.append(uri)

        text = "\n".join(lines)
        if links:
            text = f"{text}\nLinks: {' '.join(links)}"
        return text
