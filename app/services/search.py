"""Web search via the Tavily REST API.

Two consumers:
- Company research for cover letters / QA: fetched lazily, cached globally in
  the ``company_research`` table (one Tavily call per company per TTL window,
  shared across all users). Failures degrade gracefully — callers get ``None``
  and generate without company context, exactly as when no key is configured.
- JD enrichment: user-confirmed fetch of a fuller/typical description for a
  thin job description (title + company query, title-only fallback).

All web text is sanitized before it can reach an LLM prompt: the ``<<<``/``>>>``
marker sequences used to fence untrusted blocks are stripped so a malicious
page can't break out of its fence.
"""

from datetime import datetime, timedelta
import re

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CompanyResearchModel

logger = structlog.get_logger()

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

MAX_RESEARCH_CHARS = 3_000
MAX_SUPPLEMENT_CHARS = 4_000
MAX_EXTRA_RESEARCH_CHARS = 3_000
_SNIPPET_CHARS = 400
# Per Q&A request, cap how many gap lookups we'll spend on the shared Tavily quota.
MAX_LOOKUP_QUERIES = 2


class SearchError(Exception):
    """Raised when the search provider fails or rejects the request."""


def search_enabled() -> bool:
    return bool(settings.tavily_api_key)


def _clean(text: str) -> str:
    """Collapse whitespace and strip prompt-fence marker sequences."""
    text = re.sub(r"<{3,}|>{3,}", "", text)
    return re.sub(r"\s+", " ", text).strip()


async def tavily_search(query: str, max_results: int = 5, include_answer: bool = True) -> dict:
    if not search_enabled():
        raise SearchError("Web search is not configured.")
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": include_answer,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(TAVILY_SEARCH_URL, json=payload)
    except httpx.HTTPError as exc:
        await logger.aerror("tavily_search_failed", error=str(exc))
        raise SearchError("Could not reach the search provider.") from exc
    if response.status_code >= 300:
        await logger.aerror(
            "tavily_search_failed",
            status_code=response.status_code,
            body=response.text[:500],
        )
        raise SearchError("The search provider rejected the request.")
    return response.json()


_JUNIOR_RE = re.compile(r"\b(intern(ship)?|junior|entry[- ]level|graduate|trainee|working student)\b", re.I)
_SENIOR_RE = re.compile(
    r"\b(lead|senior|sr\.?|principal|staff|head of|director|manager|vp|chief|architect)\b", re.I
)
_HIGH_YEARS_RE = re.compile(r"\b([3-9]|\d{2,})\s*\+?\s*(?:years?|yrs)\b", re.I)


def _seniority(text: str) -> str | None:
    """Rough seniority class of a job title/snippet: 'junior', 'senior', or None."""
    if _JUNIOR_RE.search(text):
        return "junior"
    if _SENIOR_RE.search(text):
        return "senior"
    return None


def _seniority_conflict(target: str | None, result_title: str) -> bool:
    found = _seniority(result_title)
    return target is not None and found is not None and found != target


def _compose_results(data: dict, max_chars: int, target_seniority: str | None = None) -> str:
    parts: list[str] = []
    answer = data.get("answer")
    if answer and isinstance(answer, str):
        parts.append(_clean(answer))
    kept = 0
    for result in data.get("results") or []:
        if kept >= 3:
            break
        title = _clean(str(result.get("title") or ""))
        # Search for "X intern at Acme" often also surfaces Acme's Lead/Senior
        # postings; their requirements ("8+ years...") would poison the
        # supplement, so results at a conflicting seniority level are dropped.
        if _seniority_conflict(target_seniority, title):
            continue
        content = _clean(str(result.get("content") or ""))[:_SNIPPET_CHARS]
        # For junior/intern roles, drop snippets demanding 3+ years experience —
        # a strong sign the snippet describes a more senior posting.
        if target_seniority == "junior" and _HIGH_YEARS_RE.search(content):
            continue
        if content:
            parts.append(f"- {title}: {content}" if title else f"- {content}")
            kept += 1
    return "\n".join(parts)[:max_chars].strip()


async def research_company(company_name: str, job_title: str | None = None) -> str | None:
    """Best-effort company research. Returns None on ANY failure — callers
    generate without company context rather than failing the request."""
    try:
        data = await tavily_search(
            f"{company_name} company products mission technology", max_results=5
        )
        text = _compose_results(data, MAX_RESEARCH_CHARS)
        if not text:
            await logger.ainfo("company_research_empty", company=company_name)
            return None
        await logger.ainfo("company_research_fetched", company=company_name, chars=len(text))
        return text
    except SearchError:
        return None
    except Exception as exc:  # malformed JSON etc. — never break the caller
        await logger.aerror("company_research_failed", company=company_name, error=str(exc))
        return None


async def enrich_job_description(
    job_title: str, company_name: str | None = None
) -> tuple[str, list[dict]]:
    """Fetch a fuller/typical description for a thin JD.

    Tries "{title} at {company} job description..." first — this often finds the
    company's own full posting on a job board — and falls back to a title-only
    query for generic typical requirements. Raises SearchError on total failure.
    """
    queries = []
    if company_name:
        queries.append(
            f"{job_title} at {company_name} job description responsibilities requirements skills"
        )
    queries.append(f"{job_title} job description responsibilities required skills technologies")

    target_seniority = _seniority(job_title)
    last_error: SearchError | None = None
    for query in queries:
        try:
            data = await tavily_search(query, max_results=5)
        except SearchError as exc:
            last_error = exc
            continue
        supplement = _compose_results(
            data, MAX_SUPPLEMENT_CHARS, target_seniority=target_seniority
        )
        if supplement:
            sources = [
                {"title": str(r.get("title") or ""), "url": str(r.get("url") or "")}
                for r in (data.get("results") or [])[:5]
                if r.get("url")
                and not _seniority_conflict(target_seniority, str(r.get("title") or ""))
            ]
            await logger.ainfo(
                "jd_enrichment_fetched", query=query, chars=len(supplement)
            )
            return supplement, sources
    if last_error is not None:
        raise last_error
    raise SearchError("No usable search results for this role.")


def _combined(row: CompanyResearchModel | None) -> str | None:
    """Base research plus any accumulated targeted facts."""
    if row is None:
        return None
    parts = [row.research]
    if row.extra_research and row.extra_research.strip():
        parts.append(row.extra_research.strip())
    return "\n".join(p for p in parts if p and p.strip()) or None


def _topic_key(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


async def _get_or_refresh_row(
    db: AsyncSession, company_name: str, job_title: str | None
) -> CompanyResearchModel | None:
    """Load the cache row, refreshing stale/missing base research in place.
    Returns None only when search is disabled / no base research could be had."""
    company_key = company_name.strip().lower()
    row = (
        await db.execute(
            select(CompanyResearchModel).where(CompanyResearchModel.company_key == company_key)
        )
    ).scalar_one_or_none()

    ttl = timedelta(days=settings.company_research_ttl_days)
    if row is not None and row.fetched_at is not None and datetime.utcnow() - row.fetched_at < ttl:
        return row

    research = await research_company(company_name.strip(), job_title)
    if research is None:
        return row  # stale row (fallback) or None

    if row is None:
        row = CompanyResearchModel(
            company_key=company_key,
            company_name=company_name.strip(),
            research=research,
            fetched_at=datetime.utcnow(),
        )
        db.add(row)
    else:
        row.company_name = company_name.strip()
        row.research = research
        row.fetched_at = datetime.utcnow()
    await db.commit()
    return row


async def get_company_research(
    db: AsyncSession, company_name: str, job_title: str | None = None
) -> str | None:
    """Global, TTL-cached company research (base + accumulated targeted facts).
    One Tavily call per company per TTL window, shared across users/applications.
    Stale rows are refreshed in place; a failed refresh falls back to stale text."""
    if not search_enabled() or not company_name or not company_name.strip():
        return None
    return _combined(await _get_or_refresh_row(db, company_name, job_title))


async def lookup_and_append_company_facts(
    db: AsyncSession,
    company_name: str,
    queries: list[str],
    job_title: str | None = None,
) -> str | None:
    """Run focused gap-lookup searches, append new facts to the company cache,
    and return the combined research (base + extra). Degrades silently — on any
    failure it returns whatever is currently cached. Queries already covered
    (in extra_topics) are skipped so the same gap isn't re-searched."""
    if not search_enabled() or not company_name or not company_name.strip():
        return None

    row = await _get_or_refresh_row(db, company_name, job_title)
    if row is None:
        # No base research and none could be fetched — nothing to anchor to.
        return None

    covered = set(row.extra_topics or [])
    appended: list[str] = []
    new_topics: list[str] = []
    for query in queries[:MAX_LOOKUP_QUERIES]:
        key = _topic_key(query)
        if not key or key in covered:
            continue
        # Scope the search to the company so a bare "products" query stays on-topic.
        scoped = query if company_name.strip().lower() in key else f"{company_name.strip()} {query}"
        try:
            data = await tavily_search(scoped, max_results=4)
            snippet = _compose_results(data, _SNIPPET_CHARS * 3)
        except SearchError:
            continue
        except Exception as exc:
            await logger.aerror("company_lookup_failed", query=scoped, error=str(exc))
            continue
        covered.add(key)
        new_topics.append(key)
        if snippet:
            appended.append(snippet)

    if new_topics:
        existing_extra = (row.extra_research or "").strip()
        combined_extra = "\n".join(p for p in [existing_extra, *appended] if p)[
            :MAX_EXTRA_RESEARCH_CHARS
        ]
        row.extra_research = combined_extra or row.extra_research
        row.extra_topics = sorted(covered)
        await db.commit()
        await logger.ainfo(
            "company_facts_appended", company=company_name, new_topics=len(new_topics)
        )

    return _combined(row)
