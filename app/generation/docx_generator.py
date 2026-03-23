from io import BytesIO
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

from app.generation.base_generator import BaseGenerator
from app.generation.styles import (
    MARGIN_TOP, MARGIN_BOTTOM, MARGIN_LEFT, MARGIN_RIGHT,
    FONT_NAME, FONT_SIZE_NAME, FONT_SIZE_CONTACT, FONT_SIZE_SECTION,
    FONT_SIZE_BODY, FONT_SIZE_ENTRY_TITLE,
    SPACE_BEFORE_SECTION, SPACE_AFTER_SECTION,
    SPACE_AFTER_ENTRY, SPACE_AFTER_BULLET,
    ALIGN_CENTER
)
from app.schemas.tailored_cv import TailoredCV, ScoredExperienceEntry, ScoredProjectEntry


class DocxGenerator(BaseGenerator):
    def generate(self, cv: TailoredCV) -> bytes:
        doc = Document()
        self._set_margins(doc)
        self._add_header(doc, cv)
        self._add_education(doc, cv)
        self._add_skills(doc, cv)
        self._add_experience_and_projects(doc, cv)
        return self._to_bytes(doc)

    def content_type(self) -> str:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def file_extension(self) -> str:
        return "docx"

    # --- private section builders ---

    def _set_margins(self, doc: Document) -> None:
        for section in doc.sections:
            section.top_margin = MARGIN_TOP
            section.bottom_margin = MARGIN_BOTTOM
            section.left_margin = MARGIN_LEFT
            section.right_margin = MARGIN_RIGHT

    def _add_header(self, doc: Document, cv: TailoredCV) -> None:
        # name — large, bold, centered
        name_para = doc.add_paragraph()
        name_para.alignment = ALIGN_CENTER
        name_para.paragraph_format.space_after = Pt(2)
        run = name_para.add_run(cv.full_name)
        run.bold = True
        run.font.name = FONT_NAME
        run.font.size = FONT_SIZE_NAME

        # contact line: phone | email | linkedin
        contact_parts = []
        if cv.phone:
            contact_parts.append(cv.phone)
        if cv.email:
            contact_parts.append(cv.email)
        if cv.linkedin:
            contact_parts.append(cv.linkedin)

        contact_para = doc.add_paragraph()
        contact_para.alignment = ALIGN_CENTER
        contact_para.paragraph_format.space_after = Pt(1)
        run = contact_para.add_run(" | ".join(contact_parts))
        run.font.name = FONT_NAME
        run.font.size = FONT_SIZE_CONTACT

        # github on its own line
        if cv.github:
            github_para = doc.add_paragraph()
            github_para.alignment = ALIGN_CENTER
            github_para.paragraph_format.space_after = Pt(4)
            run = github_para.add_run(cv.github)
            run.font.name = FONT_NAME
            run.font.size = FONT_SIZE_CONTACT

    def _add_section_heading(self, doc: Document, title: str) -> None:
        """
        Adds a section heading with a full-width bottom border line
        matching your CV's EDUCATION, SKILLS, EXPERIENCE AND PROJECTS style.
        """
        para = doc.add_paragraph()
        para.paragraph_format.space_before = SPACE_BEFORE_SECTION
        para.paragraph_format.space_after = SPACE_AFTER_SECTION
        run = para.add_run(title)
        run.bold = False
        run.font.name = FONT_NAME
        run.font.size = FONT_SIZE_SECTION

        # add bottom border to paragraph via XML — this is the line under
        # each section heading in your CV
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "000000")
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _add_education(self, doc: Document, cv: TailoredCV) -> None:
        self._add_section_heading(doc, "EDUCATION")

        for entry in cv.education:
            # first line: "Institution ||Faculty|| GPA: x.xx" with date right-aligned
            # achieved via a paragraph with a right-aligned tab stop
            para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(1)
            self._set_right_tab(para)

            # institution + faculty + gpa bold
            parts = [entry.institution]
            if entry.faculty:
                parts.append(entry.faculty)
            if entry.gpa:
                parts.append(f"GPA: {entry.gpa}")

            run = para.add_run(" ||".join(parts))
            run.bold = True
            run.font.name = FONT_NAME
            run.font.size = FONT_SIZE_BODY

            # date right-aligned via tab
            date_str = self._format_date_range(entry.date_range)
            tab_run = para.add_run(f"\t{date_str}")
            tab_run.bold = True
            tab_run.font.name = FONT_NAME
            tab_run.font.size = FONT_SIZE_BODY

            # second line: "Major: field" in italic
            major_para = doc.add_paragraph()
            major_para.paragraph_format.space_after = Pt(2)
            run = major_para.add_run(f"Major: {entry.field}")
            run.italic = True
            run.font.name = FONT_NAME
            run.font.size = FONT_SIZE_BODY

    def _add_skills(self, doc: Document, cv: TailoredCV) -> None:
        self._add_section_heading(doc, "SKILLS")

        for category in cv.skills:
            para = doc.add_paragraph(style="List Bullet")
            para.paragraph_format.space_after = SPACE_AFTER_BULLET

            # bold category name inline
            run = para.add_run(f"{category.category}: ")
            run.bold = True
            run.font.name = FONT_NAME
            run.font.size = FONT_SIZE_BODY

            # plain skills list
            run = para.add_run(", ".join(category.skills))
            run.bold = False
            run.font.name = FONT_NAME
            run.font.size = FONT_SIZE_BODY

        # certifications as nested bullets under skills
        if cv.education and any(
            hasattr(e, "certifications") for e in cv.education
        ):
            pass  # handled separately if needed

    def _add_experience_and_projects(
        self, doc: Document, cv: TailoredCV
    ) -> None:
        self._add_section_heading(doc, "EXPERIENCE AND PROJECTS")

        for entry in cv.experience:
            self._add_experience_entry(doc, entry)

        for entry in cv.projects:
            self._add_project_entry(doc, entry)

    def _add_experience_entry(
        self, doc: Document, entry: ScoredExperienceEntry
    ) -> None:
        # "Title: Company (Location)"  with date right-aligned
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(2)
        self._set_right_tab(para)

        title_run = para.add_run(f"{entry.title}:")
        title_run.bold = True
        title_run.font.name = FONT_NAME
        title_run.font.size = FONT_SIZE_ENTRY_TITLE

        company_parts = []
        if entry.company:
            company_parts.append(entry.company)
        if entry.location:
            company_parts.append(f"({entry.location})")

        company_run = para.add_run(f" {' '.join(company_parts)}")
        company_run.italic = True
        company_run.font.name = FONT_NAME
        company_run.font.size = FONT_SIZE_ENTRY_TITLE

        date_str = self._format_date_range(entry.date_range)
        date_run = para.add_run(f"\t{date_str}")
        date_run.font.name = FONT_NAME
        date_run.font.size = FONT_SIZE_ENTRY_TITLE

        for bullet in entry.bullets:
            self._add_bullet(doc, bullet)

        # spacing after entry
        doc.paragraphs[-1].paragraph_format.space_after = SPACE_AFTER_ENTRY

    def _add_project_entry(
        self, doc: Document, entry: ScoredProjectEntry
    ) -> None:
        # "Name: *context/description*"  with date right-aligned
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(2)
        self._set_right_tab(para)

        name_run = para.add_run(f"{entry.name}:")
        name_run.bold = True
        name_run.font.name = FONT_NAME
        name_run.font.size = FONT_SIZE_ENTRY_TITLE

        if entry.description:
            desc_run = para.add_run(f" {entry.description}")
            desc_run.italic = True
            desc_run.font.name = FONT_NAME
            desc_run.font.size = FONT_SIZE_ENTRY_TITLE

        if entry.date_range and entry.date_range.start:
            date_run = para.add_run(f"\t{entry.date_range.start}")
            date_run.font.name = FONT_NAME
            date_run.font.size = FONT_SIZE_ENTRY_TITLE

        for bullet in entry.bullets:
            self._add_bullet(doc, bullet)

        doc.paragraphs[-1].paragraph_format.space_after = SPACE_AFTER_ENTRY

    def _add_bullet(self, doc: Document, text: str) -> None:
        para = doc.add_paragraph(style="List Bullet")
        para.paragraph_format.space_after = SPACE_AFTER_BULLET
        run = para.add_run(text)
        run.font.name = FONT_NAME
        run.font.size = FONT_SIZE_BODY

    def _set_right_tab(self, para) -> None:
        """
        Sets a right-aligned tab stop at the right margin
        so dates can be right-aligned on the same line as titles.
        """
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        from docx.shared import Inches

        pPr = para._p.get_or_add_pPr()
        tabs = OxmlElement("w:tabs")
        tab = OxmlElement("w:tab")
        tab.set(qn("w:val"), "right")
        # 6.5 inches = full text width with 0.75in margins on 8.5in page
        tab.set(qn("w:pos"), "9360")
        tabs.append(tab)
        pPr.append(tabs)

    def _format_date_range(self, date_range) -> str:
        if not date_range:
            return ""
        if date_range.end:
            return f"{date_range.start} – {date_range.end}"
        return date_range.start

    def _to_bytes(self, doc: Document) -> bytes:
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.read()