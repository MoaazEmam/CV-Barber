import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class SectionType(str,Enum):
    EXPERIENCE = "experience"
    PROJECT = "project"
    EDUCATION = "education"
    SKILL = "skill"
    CERTIFICATION = "certification"

def coerce_date_range(v):
    """Tolerate the loose date shapes LLMs emit: a bare string ("Sep 2020 – Mar
    2023", "2021 - Present", "2020") becomes {start, end}; anything else passes
    through for normal validation."""
    if isinstance(v, str):
        text = v.strip()
        if not text:
            return None
        parts = re.split(r"\s*(?:–|—|->|→|\bto\b|-)\s*", text, maxsplit=1)
        start = parts[0].strip() or None
        end = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        return {"start": start or text, "end": end}
    return v


def coerce_bullets(v):
    """Bullets as a bare string (prose CVs) or with null items → clean list[str]."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None]
    return [str(v)]


def coerce_skills(v):
    """Skills may arrive as a flat list of strings instead of categorized
    {category, skills} objects; wrap flat items under one generic category."""
    if v is None:
        return []
    if not isinstance(v, list):
        return v
    flat = [x for x in v if isinstance(x, str)]
    structured = [x for x in v if isinstance(x, dict)]
    out = list(structured)
    if flat:
        out.append({"category": "Skills", "skills": flat})
    return out


_URL_RE = re.compile(r"https?://\S+")


def _clean_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


_KNOWN_LINK_LABELS = {
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "bitbucket.org": "Bitbucket",
    "linkedin.com": "LinkedIn",
    "scholar.google.com": "Google Scholar",
    "x.com": "Twitter",
    "twitter.com": "Twitter",
    "stackoverflow.com": "Stack Overflow",
    "medium.com": "Medium",
    "dev.to": "Dev.to",
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "orcid.org": "ORCID",
    "kaggle.com": "Kaggle",
    "youtube.com": "YouTube",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "researchgate.net": "ResearchGate",
    "leetcode.com": "LeetCode",
    "hackerrank.com": "HackerRank",
}


def friendly_link_label(url) -> str:
    """A human description for a URL so links render as text, never raw URLs
    (e.g. "https://scholar.google.com/…" → "Google Scholar"). Known sites get a
    proper name; anything else falls back to the bare host (no scheme/path)."""
    if not url:
        return ""
    host = str(url).strip()
    host = re.sub(r"^[a-zA-Z][\w+.-]*://", "", host)  # strip scheme
    host = host.split("/")[0].split("@")[-1].split(":")[0].lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return str(url)
    for domain, label in _KNOWN_LINK_LABELS.items():
        if host == domain or host.endswith("." + domain):
            return label
    return host


def coerce_links(v):
    """Normalise arbitrary profile/contact links into ``{label, url}`` dicts.

    Catches every link that has no dedicated field (Portfolio, Twitter/X, Google
    Scholar, ORCID, StackOverflow, Behance, Medium, …) so it is never dropped.
    Accepts bare URL strings or objects ({label/name/text, url/href/link})."""
    if v is None:
        return []
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list):
        v = [v]
    out = []
    for item in v:
        if isinstance(item, str):
            url = item.strip()
            if url:
                out.append({"label": None, "url": url})
        elif isinstance(item, dict):
            url = _clean_str(item.get("url") or item.get("href") or item.get("link"))
            label = _clean_str(
                item.get("label") or item.get("name") or item.get("text") or item.get("title")
            )
            if url:
                out.append({"label": label, "url": url})
    return out


def coerce_certifications(v):
    """Normalise certifications into a list of ``{name, issuer, date, url}`` dicts.

    Accepts the many shapes an LLM (or older stored data) emits:
    - a bare string ("AWS Certified Solutions Architect") → name; any embedded
      URL is split out into ``url`` so the link is never thrown away;
    - an object ({name/title, issuer/organization, date/year, url/link/
      credential_url}) → mapped field-by-field.
    Entries with neither a name nor a URL are dropped.
    """
    if v is None:
        return []
    if not isinstance(v, list):
        v = [v]
    out = []
    for c in v:
        if isinstance(c, dict):
            name = _clean_str(c.get("name") or c.get("title") or c.get("certification"))
            issuer = _clean_str(c.get("issuer") or c.get("organization") or c.get("authority"))
            date = _clean_str(c.get("date") or c.get("year") or c.get("issued"))
            url = _clean_str(
                c.get("url") or c.get("link") or c.get("credential_url")
                or c.get("credential") or c.get("verify")
            )
            if not name and url:
                name = url
            if name or url:
                out.append({"name": name or url, "issuer": issuer, "date": date, "url": url})
        elif c is not None:
            text = str(c).strip()
            if not text:
                continue
            match = _URL_RE.search(text)
            url = match.group(0).rstrip(").,;]") if match else None
            name = text
            if url:
                name = _URL_RE.sub("", text).strip(" -–—|:•·()[]").strip()
                name = name or url
            out.append({"name": name, "issuer": None, "date": None, "url": url})
    return out


class DateRange(BaseModel):
    # Optional: dateless entries (e.g. personal/course projects) are common, and
    # the LLM often emits date_range={"start": null}. Tolerate it rather than
    # failing the whole parse. Matches the documented "dateless entries validate".
    start: Optional[str] = Field(
        default=None, description="e.g. 'Sep 2023' or '2022'"
    )
    end: Optional[str] = Field(
        default=None,
        description="None means present/current"
    )

class ExperienceEntry(BaseModel):
    title: str = Field(description="Job title")
    company: Optional[str]=None
    location: Optional[str] = None
    # Optional: dateless roles (freelance, ongoing) are common; don't fail the parse.
    date_range: Optional[DateRange] = None
    # Optional: prose/paragraph CVs may have no bullets, or keep prose as one bullet.
    bullets: list[str] = Field(
        default_factory=list,
        description="Each bullet is one accomplishment, no leading dash",
    )

    _coerce_date_range = field_validator("date_range", mode="before")(coerce_date_range)
    _coerce_bullets = field_validator("bullets", mode="before")(coerce_bullets)

class ProjectEntry(BaseModel):
    name: str
    description: Optional[str] = None
    tech_stack: list[str] = Field(
        default_factory=list, description="e.g. ['Python', 'FastAPI', 'PostgreSQL']"
    )
    bullets: list[str] = Field(
        default_factory=list,
        description="What you built, what it does, results if any",
    )
    url: Optional[str] = None
    date_range: Optional[DateRange] = None

    _coerce_date_range = field_validator("date_range", mode="before")(coerce_date_range)
    _coerce_bullets = field_validator("bullets", mode="before")(coerce_bullets)

class EducationEntry(BaseModel):
    institution: str
    degree: Optional[str]=None
    faculty: Optional[str]=None
    # Optional: bootcamps / high-school / certificate programs often have no field.
    field: Optional[str] = None
    minor: Optional[str] = None
    honors: Optional[str] = None
    # Optional: dateless education entries shouldn't fail the parse.
    date_range: Optional[DateRange] = None
    gpa: Optional[str] = None
    relevant_courses: list[str] = Field(default_factory=list)

    _coerce_date_range = field_validator("date_range", mode="before")(coerce_date_range)

class SkillCategory(BaseModel):
    # Defaulted: LLMs sometimes emit uncategorized skill groups.
    category: str = Field(
        default="Skills", description="e.g. 'Languages', 'Frameworks', 'Tools'"
    )
    skills: list[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, v):
        return v if isinstance(v, str) and v.strip() else "Skills"

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skill_items(cls, v):
        return coerce_bullets(v)


class Link(BaseModel):
    """A profile/contact link with no dedicated field. ``label`` is the visible
    text (e.g. "Portfolio", "Google Scholar"); ``url`` is the destination."""
    label: Optional[str] = None
    url: str

    @property
    def display(self) -> str:
        """The visible link text: the given label, else a friendly name derived
        from the URL — never the raw URL."""
        return self.label or friendly_link_label(self.url)

    def __str__(self) -> str:
        return self.display


class CertificationEntry(BaseModel):
    """A certification, licence, or professional credential. ``url`` preserves any
    verification/badge/credential link so it is never dropped on parse or render."""
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None

    def __str__(self) -> str:
        # Keeps `{{ c }}` working in templates written before certifications
        # became structured (renders "Name — Issuer (Date)").
        s = self.name
        if self.issuer:
            s += f" — {self.issuer}"
        if self.date:
            s += f" ({self.date})"
        return s


class AdditionalEntry(BaseModel):
    """A flexible row inside a non-standard section (an award, a language, a
    leadership role…). Every field is optional so any block shape round-trips.

    Validators coerce the loose shapes LLMs emit (a bullet as a bare string, a
    detail as a list) so best-effort preservation never fails the whole parse."""
    heading: Optional[str] = Field(default=None, description="the item's main label/title")
    subheading: Optional[str] = Field(
        default=None, description="org, qualifier, or a right-aligned tag e.g. 'First Place (2022)'"
    )
    location: Optional[str] = None
    date_range: Optional[DateRange] = None
    bullets: list[str] = Field(default_factory=list)
    detail: Optional[str] = Field(
        default=None, description="free text when the block isn't entry-shaped, e.g. a Languages line"
    )
    url: Optional[str] = Field(
        default=None, description="any link attached to the item, e.g. a publication DOI or project URL"
    )

    _coerce_bullets = field_validator("bullets", mode="before")(coerce_bullets)
    _coerce_date_range = field_validator("date_range", mode="before")(coerce_date_range)

    @field_validator("detail", mode="before")
    @classmethod
    def _coerce_detail(cls, v):
        if isinstance(v, list):
            return "; ".join(str(x) for x in v if x is not None)
        return v


class AdditionalSection(BaseModel):
    """Any CV section the structured schema does not model explicitly (Honors &
    Awards, Languages, Leadership & Community, standalone Coursework, Volunteering,
    Training…), preserved verbatim so a template that supports it can render it."""
    title: str = Field(description="the section heading exactly as written")
    entries: list[AdditionalEntry] = Field(default_factory=list)

    @field_validator("entries", mode="before")
    @classmethod
    def _coerce_entries(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            v = [v]
        if not isinstance(v, list):
            return []
        out = []
        for e in v:
            if isinstance(e, str):
                out.append({"detail": e})
            elif isinstance(e, dict):
                out.append(e)
        return out


def _norm_url(u) -> str:
    """Normalise a URL for equality: drop scheme, leading www., trailing slash, and
    case — so "https://www.linkedin.com/in/x" == "linkedin.com/in/x/"."""
    s = (u or "").strip().lower()
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s)
    if s.startswith("www."):
        s = s[4:]
    return s.rstrip("/")


# Section headings that are really contact links, not content sections.
_LINK_SECTION_RE = re.compile(
    r"^\s*(links?|socials?|social media|profiles?|online|contacts?|connect|find me)\b", re.I
)


def fold_link_sections_into_links(obj):
    """A CV section titled "Links"/"Social"/"Profiles"/"Contact" is contact info,
    not a content section. Move its URLs into ``obj.links`` (so they then dedupe
    against linkedin/github/website via prune) and drop the section, preventing a
    duplicate links block in the rendered CV. Email/phone (mailto:/tel:) are skipped
    — they have dedicated fields."""
    sections = getattr(obj, "additional_sections", None)
    links = getattr(obj, "links", None)
    if not sections or links is None:
        return obj
    kept = []
    for sec in sections:
        if not _LINK_SECTION_RE.match(sec.title or ""):
            kept.append(sec)
            continue
        for entry in sec.entries or []:
            url = _clean_str(entry.url)
            if not url:
                for text in (entry.heading, entry.subheading, entry.detail, " ".join(entry.bullets or [])):
                    match = _URL_RE.search(text or "")
                    if match:
                        url = match.group(0).rstrip(").,;]")
                        break
            if not url or url.lower().startswith(("mailto:", "tel:")):
                continue
            obj.links.append(Link(label=_clean_str(entry.heading) or _clean_str(entry.subheading), url=url))
    obj.additional_sections = kept
    return obj


def prune_duplicate_links(obj):
    """Remove from ``obj.links`` any URL already claimed by a dedicated field
    (linkedin/github/website) or by a specific item (a certification, project, or
    additional-section entry). Guarantees the ONE-PLACE rule for URLs even when the
    LLM duplicates a credential link into the top-level links list."""
    links = getattr(obj, "links", None)
    if not links:
        return obj
    claimed = set()
    for attr in ("linkedin", "github", "website"):
        val = getattr(obj, attr, None)
        if val:
            claimed.add(_norm_url(val))
    for cert in getattr(obj, "certifications", None) or []:
        if getattr(cert, "url", None):
            claimed.add(_norm_url(cert.url))
    for proj in getattr(obj, "projects", None) or []:
        if getattr(proj, "url", None):
            claimed.add(_norm_url(proj.url))
    for sec in getattr(obj, "additional_sections", None) or []:
        for entry in getattr(sec, "entries", None) or []:
            if getattr(entry, "url", None):
                claimed.add(_norm_url(entry.url))
    obj.links = [l for l in links if _norm_url(l.url) not in claimed]
    return obj


_CERT_WORD = re.compile(r"certificat\w*|certif\w*|licen[cs]\w*", re.I)


def tidy_combined_section_titles(obj):
    """When a combined heading like "Awards & Certificates" had its certificates
    pulled into the ``certifications`` field, the leftover section should not still
    advertise certificates. Strip the now-empty category from such titles so the
    output reads "Awards" instead of "Awards & Certificates"."""
    if not (getattr(obj, "certifications", None)):
        return obj
    for sec in getattr(obj, "additional_sections", None) or []:
        title = sec.title or ""
        if not _CERT_WORD.search(title):
            continue
        new = re.sub(r"\s*[&/+]+\s*(?:certificat\w*|certif\w*|licen[cs]\w*)\b", "", title, flags=re.I)
        new = re.sub(r"\b(?:certificat\w*|certif\w*|licen[cs]\w*)\s*[&/+]+\s*", "", new, flags=re.I)
        new = new.strip(" &/+-—|")
        if new and new.lower() != title.lower():
            sec.title = new
    return obj


def coerce_additional_sections(v):
    """Normalise the ``additional_sections`` value an LLM emits into a clean list of
    section dicts. A dict (``{title: entries}``) becomes a list; non-dict / titleless
    items are dropped. Tolerant by design — these sections are best-effort extras."""
    if v is None:
        return []
    if isinstance(v, dict):
        return [{"title": k, "entries": val} for k, val in v.items()]
    if not isinstance(v, list):
        return []
    return [s for s in v if isinstance(s, dict) and s.get("title")]