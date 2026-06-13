"""Templatize a filled-in custom CV template.

Most users upload the *finished* CV they compiled on Overleaf — a .tex/.html
document with their real name, bullets and dates hardcoded as literal text and
no placeholders. The render pipeline only substitutes data where Jinja
placeholders exist, so such an upload would render the same PDF for every job.

``TemplateConverter`` uses the LLM to convert that filled-in document into a
reusable Jinja template: it preserves the user's exact preamble/styling/layout
but replaces the literal CV content with ``cv.*`` placeholders (and collapses
repeated entries into ``for`` loops). The output uses the same delimiter
convention as the example templates — ``\\VAR{ cv.* }`` / ``\\BLOCK{}`` for
LaTeX, ``{{ cv.* }}`` / ``{% %}`` for HTML — so it flows through the existing
render path unchanged.

Two things keep the conversion reliable: a known-good example of the target
convention is shown to the model as a reference, and a caller-supplied
``validate`` callback (the sandbox test-render) drives a compile-repair loop —
when the converted output fails to compile, the compiler error is fed back to
the model to fix, up to ``max_repairs`` times.
"""
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm

log = structlog.get_logger()

# A template that fills with CV data references a `cv.*` field inside a
# placeholder (`\VAR{ cv.* }` for LaTeX, `{{ cv.* }}` for HTML). Shared with the
# upload route so the "has placeholders?" check and the converter agree.
PLACEHOLDER_RE = re.compile(r"(\\VAR\{|\{\{)[^{}]*\bcv\b")

# A genuine templatization references many distinct `cv.*` fields and loops over
# the list sections. A result with a single `cv.full_name` and everything else
# hardcoded passes PLACEHOLDER_RE but still renders the same CV for every job —
# these two patterns gate that out.
_CV_FIELD_RE = re.compile(r"\bcv\.([A-Za-z_][\w.]*)")  # distinct cv.<path> references
_CV_LOOP_RE = re.compile(r"\bfor\s+\w+\s+in\s+cv\.\w+")  # for x in cv.experience/...
# Minimum distinct cv.* field paths a real template must reference (name, email,
# summary, plus per-entry fields inside at least one loop comfortably exceed this).
_MIN_CV_FIELDS = 5


def _is_substantially_templatized(source: str) -> bool:
    """True when ``source`` looks like a real reusable template, not a near-verbatim
    echo with one placeholder bolted on: it must reference several distinct ``cv.*``
    fields AND loop over at least one list section (experience/projects/...)."""
    distinct_fields = {m.group(1) for m in _CV_FIELD_RE.finditer(source)}
    return len(distinct_fields) >= _MIN_CV_FIELDS and _CV_LOOP_RE.search(source) is not None

# A real résumé .tex/.html is a few KB. Above this we skip conversion rather than
# risk an oversized prompt or a corrupting truncation of the template.
MAX_CONVERT_CHARS = 40_000

# Known-good reference templates (the target convention) shown to the model.
_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "generation" / "templates" / "examples"
_EXAMPLE_FILES = {"tex": "cv_example.tex", "html": "cv_example.html"}

# Prompt filling: the prompt files are full of literal LaTeX braces, so str.format
# is unusable. Substitute only our explicit {token}s in a single pass — injected
# values (template source, examples) are never re-scanned for tokens.
_TOKEN_RE = re.compile(r"\{(format|source|example|broken|error)\}")


def _fill(template: str, **values: str) -> str:
    return _TOKEN_RE.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def _load_example(fmt: str) -> str:
    path = _EXAMPLES_DIR / _EXAMPLE_FILES.get(fmt, "cv_example.tex")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _strip_fences(text: str) -> str:
    """Remove a wrapping markdown code fence (```` ```latex ``` ````) the model
    may add around the template source."""
    text = text.strip()
    if text.startswith("```"):
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1:]
        stripped = text.rstrip()
        if stripped.endswith("```"):
            text = stripped[:-3]
    return text.strip()


class TemplateConverter:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create("convert")
        self._system = load_prompt("template_convert_system")
        self._user_template = load_prompt("template_convert_user")
        self._repair_template = load_prompt("template_repair_user")

    async def convert(
        self,
        source: str,
        fmt: str,
        *,
        validate: Callable[[str], Awaitable[None]] | None = None,
        max_repairs: int = 1,
    ) -> str:
        """Convert a filled-in template ``source`` (``fmt`` in {"tex","html"})
        into a Jinja template.

        If ``validate`` is given it is awaited on the candidate (the sandbox
        test-render); when it raises, the error is fed back to the model to repair
        the template, up to ``max_repairs`` times. The final ``validate`` failure
        propagates unchanged (the route catches it and falls back to the original).
        Raises ``LLMValidationError`` if a generation has no ``cv.*`` placeholders.
        """
        candidate = await self._generate(source, fmt)
        if validate is None:
            return candidate

        for attempt in range(max_repairs + 1):
            try:
                await validate(candidate)
                return candidate
            except Exception as e:  # compile/render failure from the callback
                if attempt == max_repairs:
                    raise
                log.info("template_convert_repairing", attempt=attempt + 1, fmt=fmt, error=str(e)[:200])
                candidate = await self._repair(source, fmt, candidate, str(e))
        return candidate  # unreachable

    @async_retry_llm(max_retries=2)
    async def _generate(self, source: str, fmt: str) -> str:
        user_prompt = _fill(
            self._user_template, format=fmt, source=source, example=_load_example(fmt)
        )
        return await self._complete_template(user_prompt)

    @async_retry_llm(max_retries=2)
    async def _repair(self, source: str, fmt: str, broken: str, error: str) -> str:
        user_prompt = _fill(
            self._repair_template, format=fmt, source=source, broken=broken, error=error[:2000]
        )
        return await self._complete_template(user_prompt)

    async def _complete_template(self, user_prompt: str) -> str:
        try:
            raw = await self._client.complete(self._system, user_prompt)
        except (LLMRateLimitError, LLMAllKeysExhaustedError):
            raise
        except Exception as e:
            raise LLMValidationError(f"Template conversion call failed: {e}") from e

        converted = _strip_fences(raw)
        if not _is_substantially_templatized(converted):
            # The model echoed the document with few/no placeholders and no loops —
            # it would still render the same CV for every job. Retryable.
            raise LLMValidationError(
                "Converted template is not substantially templatized "
                "(needs several cv.* fields and a loop over a list section)."
            )
        return converted
