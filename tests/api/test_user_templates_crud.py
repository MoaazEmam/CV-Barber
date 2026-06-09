"""CRUD + dedup for custom user templates (app.api.dependencies)."""
import pytest

from app.api.dependencies import (
    create_user_template,
    delete_user_template,
    get_user_template,
    get_user_template_by_hash,
    list_user_templates,
)
from app.pipeline.dedup import text_hash

TEX_SOURCE = r"\documentclass{article}\begin{document}\VAR{ cv.full_name }\end{document}"


class TestUserTemplateDedup:
    async def test_get_by_hash_returns_created_row(self, db_session, test_user):
        h = text_hash(TEX_SOURCE)
        tid = await create_user_template(
            db_session, test_user.id, "cv.tex", "tex", TEX_SOURCE, source_hash=h
        )
        found = await get_user_template_by_hash(db_session, test_user.id, h)
        assert found is not None
        assert found.id == tid
        assert found.source_hash == h

    async def test_get_by_hash_misses_for_different_hash(self, db_session, test_user):
        await create_user_template(
            db_session, test_user.id, "cv.tex", "tex", TEX_SOURCE,
            source_hash=text_hash(TEX_SOURCE),
        )
        assert await get_user_template_by_hash(db_session, test_user.id, text_hash("other")) is None

    async def test_whitespace_variants_share_hash(self):
        # Trivial-whitespace re-uploads (e.g. re-export from Overleaf) dedup together.
        assert text_hash(TEX_SOURCE) == text_hash(TEX_SOURCE + "  \n")

    async def test_delete_removes_template(self, db_session, test_user):
        h = text_hash(TEX_SOURCE)
        tid = await create_user_template(
            db_session, test_user.id, "cv.tex", "tex", TEX_SOURCE, source_hash=h
        )
        await delete_user_template(db_session, tid, test_user.id)
        assert await get_user_template(db_session, tid, test_user.id) is None
        assert await get_user_template_by_hash(db_session, test_user.id, h) is None
        assert await list_user_templates(db_session, test_user.id) == []

    async def test_delete_missing_raises_keyerror(self, db_session, test_user):
        import uuid

        with pytest.raises(KeyError):
            await delete_user_template(db_session, uuid.uuid4(), test_user.id)
