"""Built-in CV template registry.

Built-in templates are HTML/Jinja2 themes rendered to PDF by WeasyPrint. Each is
single-column and ATS-optimized (see app/generation/templates/_macros.html). Custom
user-uploaded templates are stored per-user in the DB, not here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

DEFAULT_BUILTIN_ID = "classic"


@dataclass(frozen=True)
class BuiltinTemplate:
    id: str
    name: str
    description: str
    filename: str
    engine: str = "html"  # all built-ins render via WeasyPrint

    @property
    def path(self) -> Path:
        return TEMPLATES_DIR / self.filename


_BUILTINS: dict[str, BuiltinTemplate] = {
    t.id: t
    for t in [
        BuiltinTemplate("classic", "Classic", "Traditional serif, centered name, ruled section headings.", "classic.html"),
        BuiltinTemplate("modern", "Modern", "Clean sans-serif with a navy accent and bold section rules.", "modern.html"),
        BuiltinTemplate("compact", "Compact", "Dense single-column layout that fits more on each page.", "compact.html"),
        BuiltinTemplate("professional", "Professional", "Elegant serif with small-caps headings and generous spacing.", "professional.html"),
        BuiltinTemplate("minimal", "Minimal", "Understated sans-serif, no rules, lots of whitespace.", "minimal.html"),
    ]
}


def list_builtins() -> list[BuiltinTemplate]:
    return list(_BUILTINS.values())


def get_builtin(template_id: str) -> BuiltinTemplate | None:
    return _BUILTINS.get(template_id)
