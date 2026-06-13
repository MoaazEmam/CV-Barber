from unittest.mock import AsyncMock, patch

import pytest

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.llm.template_converter import (
    TemplateConverter,
    _is_substantially_templatized,
    _strip_fences,
)

# A substantially-templatized result the fake client can return: several distinct
# cv.* fields and a loop over a list section (passes the new acceptance gate).
TEX_TEMPLATE = (
    r"\documentclass{article}\begin{document}"
    r"\VAR{ cv.full_name } \VAR{ cv.email } \VAR{ cv.phone } \VAR{ cv.tailored_summary }"
    r"\BLOCK{ for exp in cv.experience }\VAR{ exp.title } \VAR{ exp.company }\BLOCK{ endfor }"
    r"\end{document}"
)
HTML_TEMPLATE = (
    "<html><body>{{ cv.full_name }} {{ cv.email }} {{ cv.phone }} {{ cv.tailored_summary }}"
    "{% for exp in cv.experience %}{{ exp.title }} {{ exp.company }}{% endfor %}</body></html>"
)
# A near-verbatim echo: one cv.* placeholder, no loop — must be rejected by the gate.
TEX_ECHO = r"\documentclass{article}\begin{document}\VAR{ cv.full_name } Jane Doe, Acme Corp\end{document}"


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        yield


def _client(*returns) -> BaseLLMClient:
    client = AsyncMock(spec=BaseLLMClient)
    if len(returns) == 1:
        client.complete.return_value = returns[0]
    else:
        client.complete.side_effect = list(returns)
    return client


class TestStripFences:
    def test_strips_language_fence(self):
        assert _strip_fences("```latex\n" + TEX_TEMPLATE + "\n```") == TEX_TEMPLATE

    def test_strips_bare_fence(self):
        assert _strip_fences("```\n" + HTML_TEMPLATE + "\n```") == HTML_TEMPLATE

    def test_passthrough_without_fence(self):
        assert _strip_fences("  " + TEX_TEMPLATE + "  ") == TEX_TEMPLATE


class TestSubstantiallyTemplatized:
    def test_accepts_looped_multi_field_tex(self):
        assert _is_substantially_templatized(TEX_TEMPLATE)

    def test_accepts_looped_multi_field_html(self):
        assert _is_substantially_templatized(HTML_TEMPLATE)

    def test_rejects_single_placeholder_echo(self):
        assert not _is_substantially_templatized(TEX_ECHO)

    def test_rejects_many_fields_but_no_loop(self):
        src = " ".join(rf"\VAR{{ cv.f{i} }}" for i in range(8))  # 8 fields, no loop
        assert not _is_substantially_templatized(src)

    def test_rejects_loop_but_too_few_fields(self):
        src = r"\BLOCK{ for x in cv.experience }\VAR{ x.title }\BLOCK{ endfor }"
        assert not _is_substantially_templatized(src)


class TestTemplateConverter:
    async def test_returns_stripped_template(self):
        converter = TemplateConverter(client=_client("```latex\n" + TEX_TEMPLATE + "\n```"))
        result = await converter.convert("hardcoded cv", "tex")
        assert result == TEX_TEMPLATE

    async def test_format_and_source_in_user_prompt(self):
        client = _client(HTML_TEMPLATE)
        converter = TemplateConverter(client=client)
        await converter.convert("UNIQUE_SOURCE_TEXT", "html")
        user_prompt = client.complete.call_args[0][1]
        assert "Format: html" in user_prompt
        assert "UNIQUE_SOURCE_TEXT" in user_prompt

    async def test_retries_when_no_placeholder_then_succeeds(self):
        client = _client("plain document with no placeholders", TEX_TEMPLATE)
        converter = TemplateConverter(client=client)
        result = await converter.convert("hardcoded cv", "tex")
        assert result == TEX_TEMPLATE
        assert client.complete.call_count == 2

    async def test_raises_when_never_adds_placeholder(self):
        client = _client("still no placeholders")
        converter = TemplateConverter(client=client)
        with pytest.raises(LLMValidationError):
            await converter.convert("hardcoded cv", "tex")

    async def test_retries_when_only_partially_templatized(self):
        # A near-verbatim echo (one cv.* field, no loop) is rejected and retried;
        # the second, properly-templatized result is accepted.
        client = _client(TEX_ECHO, TEX_TEMPLATE)
        converter = TemplateConverter(client=client)
        result = await converter.convert("hardcoded cv", "tex")
        assert result == TEX_TEMPLATE
        assert client.complete.call_count == 2

    async def test_raises_when_only_partially_templatized_throughout(self):
        client = _client(TEX_ECHO)
        converter = TemplateConverter(client=client)
        with pytest.raises(LLMValidationError):
            await converter.convert("hardcoded cv", "tex")

    @pytest.mark.parametrize("exc", [LLMRateLimitError(), LLMAllKeysExhaustedError()])
    async def test_rate_limit_errors_propagate(self, exc):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete.side_effect = exc
        converter = TemplateConverter(client=client)
        with pytest.raises(type(exc)):
            await converter.convert("hardcoded cv", "tex")
        # Not retried — rate-limit/exhaustion pass straight through.
        assert client.complete.call_count == 1

    async def test_reference_example_in_prompt(self):
        client = _client(TEX_TEMPLATE)
        await TemplateConverter(client=client).convert("src", "tex")
        user_prompt = client.complete.call_args[0][1]
        # The known-good example template is included as a reference.
        assert "REFERENCE_TEMPLATE_START" in user_prompt
        assert "\\resumeSubheading" in user_prompt  # from cv_example.tex


class TestRepairLoop:
    async def test_repairs_on_compile_failure(self):
        # generate returns a (placeholder-valid) template that fails to compile
        # once; the repair returns a fixed one that validates.
        client = _client(TEX_TEMPLATE, TEX_TEMPLATE)
        renders = {"n": 0}

        async def validate(_src):
            renders["n"] += 1
            if renders["n"] == 1:
                raise RuntimeError("LaTeX Error: missing \\item")

        result = await TemplateConverter(client=client).convert(
            "src", "tex", validate=validate, max_repairs=1
        )
        assert result == TEX_TEMPLATE
        assert client.complete.call_count == 2  # generate + one repair
        assert renders["n"] == 2  # validated again after repair

    async def test_no_repair_when_first_compiles(self):
        client = _client(TEX_TEMPLATE)

        async def validate(_src):
            return None

        await TemplateConverter(client=client).convert(
            "src", "tex", validate=validate, max_repairs=1
        )
        assert client.complete.call_count == 1  # generate only, no repair

    async def test_render_error_propagates_after_repairs_exhausted(self):
        client = _client(TEX_TEMPLATE, TEX_TEMPLATE)

        async def validate(_src):
            raise RuntimeError("still broken")

        with pytest.raises(RuntimeError):
            await TemplateConverter(client=client).convert(
                "src", "tex", validate=validate, max_repairs=1
            )
        assert client.complete.call_count == 2  # generate + one repair, then give up
