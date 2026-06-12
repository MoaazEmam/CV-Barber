"""Admin metrics + feedback review endpoints (app.api.routes.admin)."""

import uuid
from datetime import datetime

from app.db.models import ApplicationModel, FeedbackModel, MasterCVModel


async def _seed_activity(db_session, user):
    cv = MasterCVModel(
        id=uuid.uuid4(),
        user_id=user.id,
        raw_file=b"x",
        file_type="pdf",
        parsed_data={},
    )
    db_session.add(cv)
    await db_session.commit()
    app_with_cl = ApplicationModel(
        id=uuid.uuid4(),
        user_id=user.id,
        master_cv_id=cv.id,
        job_title="Engineer",
        company_name="Acme",
        job_description="jd",
        tailored_cv_data={},
        cover_letter="Dear hiring manager",
        template_id="builtin:classic",
    )
    app_without_cl = ApplicationModel(
        id=uuid.uuid4(),
        user_id=user.id,
        master_cv_id=cv.id,
        job_title="Engineer 2",
        company_name="Acme",
        job_description="jd",
        tailored_cv_data={},
    )
    db_session.add_all([app_with_cl, app_without_cl])
    await db_session.commit()
    return cv


async def _seed_feedback(db_session, user, **kw):
    fb = FeedbackModel(
        id=uuid.uuid4(),
        user_id=user.id,
        type=kw.get("type", "bug"),
        message=kw.get("message", "Something broke"),
        page_context=kw.get("page_context"),
        status=kw.get("status", "open"),
        created_at=kw.get("created_at", datetime.utcnow()),
    )
    db_session.add(fb)
    await db_session.commit()
    return fb


class TestMetricsAccess:
    async def test_anonymous_401(self, client):
        resp = await client.get("/api/admin/metrics")
        assert resp.status_code == 401

    async def test_regular_user_403(self, client, user_headers):
        resp = await client.get("/api/admin/metrics", headers=user_headers)
        assert resp.status_code == 403

    async def test_superuser_200(self, client, admin_headers):
        resp = await client.get("/api/admin/metrics", headers=admin_headers)
        assert resp.status_code == 200


class TestMetricsContent:
    async def test_counts_match_seeded_rows(self, client, db_session, test_user, admin_headers):
        await _seed_activity(db_session, test_user)
        resp = await client.get("/api/admin/metrics", headers=admin_headers)
        data = resp.json()
        assert data["total_users"] == 2
        assert data["verified_users"] == 1  # superuser fixture is verified
        assert data["unverified_users"] == 1
        assert data["total_master_cvs"] == 1
        assert data["total_applications"] == 2
        assert data["cover_letters_generated"] == 1
        assert data["active_users_7d"] == 1
        assert data["avg_applications_per_user"] == 1.0
        assert len(data["signups_per_day"]) == 30
        assert len(data["activity_per_day"]) == 30
        assert len(data["peak_hours"]) == 24
        # 3 activity events today (1 CV + 2 apps)
        assert sum(d["count"] for d in data["activity_per_day"]) == 3
        assert sum(h["count"] for h in data["peak_hours"]) == 3
        labels = {t["label"]: t["count"] for t in data["template_popularity"]}
        assert labels == {"builtin:classic": 1, "default": 1}


class TestAdminFeedback:
    async def test_regular_user_403(self, client, user_headers):
        resp = await client.get("/api/admin/feedback", headers=user_headers)
        assert resp.status_code == 403

    async def test_list_includes_submitter(self, client, db_session, test_user, admin_headers):
        await _seed_feedback(db_session, test_user, page_context="/upload")
        resp = await client.get("/api/admin/feedback", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["user_email"] == "test@cvbarber.dev"
        assert items[0]["username"] == "testuser"
        assert items[0]["page_context"] == "/upload"

    async def test_status_filter(self, client, db_session, test_user, admin_headers):
        await _seed_feedback(db_session, test_user, status="open")
        await _seed_feedback(db_session, test_user, status="resolved")
        open_items = (
            await client.get("/api/admin/feedback?status=open", headers=admin_headers)
        ).json()
        assert [i["status"] for i in open_items] == ["open"]

    async def test_patch_status(self, client, db_session, test_user, admin_headers):
        fb = await _seed_feedback(db_session, test_user)
        resp = await client.patch(
            f"/api/admin/feedback/{fb.id}", json={"status": "resolved"}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_patch_missing_404(self, client, admin_headers):
        resp = await client.patch(
            f"/api/admin/feedback/{uuid.uuid4()}",
            json={"status": "resolved"},
            headers=admin_headers,
        )
        assert resp.status_code == 404
