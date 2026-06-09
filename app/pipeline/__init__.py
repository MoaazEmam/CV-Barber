"""CV parsing pipeline.

A shared layer (raw-text extraction, dedup, structure identification, schema
extraction) produces the structured CV from an upload. PDF inputs render via a
user-chosen template (HTML/WeasyPrint or .tex/Tectonic); DOCX inputs render via
in-place edit ("keep original") or those same templates. Rendering is dispatched
by :mod:`app.generation.render_dispatch`.
"""
