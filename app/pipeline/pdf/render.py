"""PDF rendering.

Fills the cached Jinja2-LaTeX template with the (section-filtered) tailored CV
and compiles it to PDF with Tectonic. Values are LaTeX-escaped automatically via
the environment's ``finalize`` hook, so templates place bare ``\\VAR{...}``.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import jinja2
from jinja2.sandbox import SandboxedEnvironment
import structlog

log = structlog.get_logger()

# Characters that must be escaped in LaTeX body text.
_LATEX_REPLACEMENTS = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def latex_escape(value) -> str:
    """Escape a value for safe inclusion in LaTeX body text."""
    if value is None or isinstance(value, jinja2.Undefined):
        return ""
    s = str(value)
    # Backslash must be replaced first, but its replacement contains braces, so
    # do backslash, then braces, then the rest to avoid double-escaping.
    s = s.replace("\\", "\udead")  # placeholder, restored last
    for char, repl in _LATEX_REPLACEMENTS[1:]:
        s = s.replace(char, repl)
    s = s.replace("\udead", r"\textbackslash{}")
    return s


# --- LaTeX template hygiene (used for custom .tex templates) ----------------
# Tectonic bundles the TeX Gyre family but NOT proprietary system fonts. When a
# template writes \setmainfont{Helvetica} (etc.), fontspec can't find it and the
# whole compile fails. Remap common system font names to bundled equivalents.
_FONT_MAP = {
    "helvetica": "TeX Gyre Heros",
    "helvetica neue": "TeX Gyre Heros",
    "arial": "TeX Gyre Heros",
    "calibri": "TeX Gyre Heros",
    "verdana": "TeX Gyre Heros",
    "tahoma": "TeX Gyre Heros",
    "segoe ui": "TeX Gyre Heros",
    "times": "TeX Gyre Termes",
    "times new roman": "TeX Gyre Termes",
    "georgia": "TeX Gyre Termes",
    "cambria": "TeX Gyre Termes",
    "garamond": "TeX Gyre Pagella",
    "courier": "TeX Gyre Cursor",
    "courier new": "TeX Gyre Cursor",
}

_FONT_CMD_RE = re.compile(
    r"(\\(?:setmainfont|setsansfont|setmonofont|newfontfamily)\b"
    r"(?:\\\w+)?\s*(?:\[[^\]]*\])?\s*\{)([^}]*)(\})"
)


def _remap_font(name: str) -> str:
    # Strip weight/style suffixes a font name may carry (e.g. "Helvetica-Bold").
    base = re.split(r"[-\s]+(?:bold|italic|oblique|light|regular|roman|md|semibold)",
                    name.strip(), flags=re.IGNORECASE)[0].strip()
    return _FONT_MAP.get(base.lower(), "TeX Gyre Heros")


def remap_fonts(tex: str) -> str:
    """Replace system font names in fontspec commands with bundled TeX Gyre fonts."""
    return _FONT_CMD_RE.sub(lambda m: f"{m.group(1)}{_remap_font(m.group(2))}{m.group(3)}", tex)


# Unescaped LaTeX comment: a `%` not preceded by a backslash, to end of line. A
# `% \VAR{...}` comment would otherwise be parsed by Jinja and crash the fill.
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def strip_latex_comments(tex: str) -> str:
    """Drop LaTeX comments before Jinja parses the template (``\\%`` is preserved)."""
    return _LATEX_COMMENT_RE.sub("", tex)


# pdfTeX-only primitives that XeTeX (Tectonic) doesn't define. Popular resume
# templates (e.g. Jake Gutierrez's) include these assuming pdfLaTeX on Overleaf;
# under XeTeX they error (`glyphtounicode: Undefined control sequence`). XeTeX is
# Unicode-native, so the glyph-to-unicode ATS hack is unnecessary — drop it.
_PDFTEX_RE = re.compile(
    r"\\input\s*\{\s*glyphtounicode\s*\}"
    r"|\\pdfgentounicode\b\s*=?\s*\d*"
    r"|\\pdfglyphtounicode\b"
    r"|\\pdfmapfile\s*\{[^}]*\}"
    r"|\\pdfmapline\s*\{[^}]*\}"
)


def strip_pdftex_primitives(tex: str) -> str:
    """Remove pdfTeX-only primitives that fail under XeTeX/Tectonic."""
    return _PDFTEX_RE.sub("", tex)


class _LenientUndefined(jinja2.ChainableUndefined):
    """Undefined that never raises — chains on attribute access and iterates empty.

    A vision-generated template may reference a field that isn't in the schema
    (e.g. ``cv.awards``). Rather than crashing the whole compile, such references
    render as nothing: ``\\VAR{...}`` → "" (via ``latex_escape``) and
    ``\\BLOCK{for x in cv.unknown}`` → an empty loop.
    """

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0


def _build_env(sandboxed: bool = False) -> jinja2.Environment:
    # User-uploaded templates render in a Jinja sandbox (blocks dunder access,
    # arbitrary attribute/callable abuse — i.e. SSTI). Built-in/trusted templates
    # use the plain environment.
    env_cls = SandboxedEnvironment if sandboxed else jinja2.Environment
    env = env_cls(
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        line_statement_prefix="%%",
        line_comment_prefix="%#",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=_LenientUndefined,
        finalize=latex_escape,
    )
    env.filters["latex"] = latex_escape
    return env


class TectonicError(RuntimeError):
    """Raised when Tectonic fails to compile the filled template."""


def render(template_tex: str, cv, *, untrusted: bool = False, timeout: int = 120) -> bytes:
    """Fill ``template_tex`` with ``cv`` and compile to PDF bytes.

    ``cv`` may be a dict or a pydantic model (both support ``cv.field`` in Jinja).
    ``untrusted=True`` (user-uploaded .tex) renders in a Jinja sandbox and compiles
    with Tectonic ``--untrusted`` (disables shell-escape / restricts file access).
    """
    # Remap system font names to bundled fonts, drop LaTeX comments (a
    # `% \VAR{...}` line would otherwise crash the Jinja fill), and strip
    # pdfTeX-only primitives that XeTeX can't compile.
    template_tex = strip_pdftex_primitives(strip_latex_comments(remap_fonts(template_tex)))
    env = _build_env(sandboxed=untrusted)
    template = env.from_string(template_tex)
    filled = template.render(cv=cv)

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "cv.tex"
        tex_path.write_text(filled, encoding="utf-8")
        cmd = ["tectonic"]
        if untrusted:
            cmd.append("--untrusted")
        cmd += [str(tex_path), "--outdir", tmpdir, "--chatter", "minimal"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as e:
            raise TectonicError("Tectonic binary not found on PATH.") from e
        except subprocess.TimeoutExpired as e:
            raise TectonicError("Tectonic compilation timed out.") from e

        pdf_path = Path(tmpdir) / "cv.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            tail = (result.stderr or result.stdout or "")[-2000:]
            log.warning("tectonic_compile_failed", returncode=result.returncode, log=tail)
            raise TectonicError(f"Tectonic failed to compile the CV:\n{tail}")

        return pdf_path.read_bytes()
