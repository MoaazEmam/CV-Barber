"""Generation package: ATS-friendly templates + unified render dispatch.

All rendering goes through :mod:`app.generation.render_dispatch` (built-in HTML
themes via WeasyPrint, custom .tex via Tectonic, or DOCX in-place edit), with
``section_filter`` and ``template_registry`` as supporting pieces.
"""
