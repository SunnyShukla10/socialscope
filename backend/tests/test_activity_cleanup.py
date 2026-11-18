"""Activity retention boundaries through authenticated API requests."""
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Organization, Project, User
from app.models.activity_event import ActivityEvent
from app.models.feedback import Feedback
from app.services.auth_service import AuthService


def headers(user):
    return {"Authorization": "Bearer " + AuthService(None).create_access_token(
        {"sub": str(user.id), "ver": user.token_version})}


@pytest.fixture
async def history(sessions, seed_org_and_user):
    org, admin, _ = seed_org_and_user
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    async with sessions() as db:
        other_org = Organization(name="Other organization", slug=str(uuid.uuid4()))
        db.add(other_org)
        await db.flush()
        member = User(organization_id=org.id, email="member@example.com", full_name="Member",
                      role="member", hashed_password=User.hash_password("test-password"))
        db.add(member)
        await db.flush()
        events = {}
        for name, organization_id, actor_id, created in [
            ("old_admin", org.id, admin.id, cutoff - timedelta(days=1)),
            ("old_member", org.id, member.id, cutoff - timedelta(days=1)),
            ("old_system", org.id, None, cutoff - timedelta(days=1)),
            ("boundary", org.id, admin.id, cutoff),
            ("recent", org.id, admin.id, cutoff + timedelta(days=1)),
            ("other_org", other_org.id, None, cutoff - timedelta(days=1)),
        ]:
            event = ActivityEvent(organization_id=organization_id, actor_user_id=actor_id,
                                  actor_label=name, action="test_event", target_type="test",
                                  created_at=created)
            db.add(event)
            await db.flush()
            events[name] = event.id
        await db.commit()
    return cutoff.isoformat(), member, events


@pytest.mark.asyncio
async def test_cleanup_preview_and_delete_are_scoped_and_audited(client, sessions, auth_headers, history):
    cutoff, _, events = history
    async with sessions() as db:
        admin = await db.scalar(select(User).where(User.role == 'admin'))
        project = Project(name='Retained research', organization_id=admin.organization_id, owner_user_id=admin.id)
        feedback = Feedback(organization_id=admin.organization_id, user_id=admin.id,
                            submitter_label=admin.email, kind='feedback', message='Retained feedback',
                            page_path='/projects')
        db.add_all([project, feedback])
        await db.commit()
        project_id, feedback_id = project.id, feedback.id
    body = {"before": cutoff}
    preview = await client.post('/api/admin/audit-log/cleanup-preview', headers=auth_headers, json=body)
    assert preview.status_code == 200 and preview.json()['matching_count'] == 3
    async with sessions() as db:
        assert len((await db.scalars(select(ActivityEvent))).all()) == 6  # Preview is read-only.
    response = await client.request('DELETE', '/api/admin/audit-log', headers=auth_headers,
                                    json={**body, 'confirmation': 'DELETE'})
    assert response.status_code == 200 and response.json()['deleted_count'] == 3
    async with sessions() as db:
        remaining = (await db.scalars(select(ActivityEvent))).all()
        ids = {event.id for event in remaining}
        assert {events['boundary'], events['recent'], events['other_org']} <= ids
        audit = next(event for event in remaining if event.action == 'activity_history_deleted')
        assert audit.actor_user_id is not None
        assert audit.extra_metadata['deleted_count'] == 3
        assert audit.extra_metadata['user_id'] is None
        assert await db.get(Project, project_id) is not None
        assert await db.get(Feedback, feedback_id) is not None


@pytest.mark.asyncio
async def test_filtered_cleanup_and_repeated_delete(client, auth_headers, history):
    cutoff, member, _ = history
    body = {'before': cutoff, 'user_id': str(member.id)}
    preview = await client.post('/api/admin/audit-log/cleanup-preview', headers=auth_headers, json=body)
    assert preview.json()['matching_count'] == 1
    for count in (1, 0):
        response = await client.request('DELETE', '/api/admin/audit-log', headers=auth_headers,
                                        json={**body, 'confirmation': 'DELETE'})
        assert response.status_code == 200 and response.json()['deleted_count'] == count
    assert (await client.post('/api/admin/audit-log/cleanup-preview', headers=auth_headers,
                              json={'before': cutoff, 'user_id': str(uuid.uuid4())})).json()['matching_count'] == 0


@pytest.mark.asyncio
async def test_cleanup_requires_admin_and_explicit_confirmation(client, auth_headers, history):
    cutoff, member, _ = history
    for request_headers in ({}, headers(member)):
        preview = await client.post('/api/admin/audit-log/cleanup-preview', headers=request_headers,
                                    json={'before': cutoff})
        deletion = await client.request('DELETE', '/api/admin/audit-log', headers=request_headers,
                                        json={'before': cutoff, 'confirmation': 'DELETE'})
        assert preview.status_code in (401, 403) and deletion.status_code in (401, 403)
    for body in ({'before': cutoff}, {'before': cutoff, 'confirmation': 'yes'},
                 {'before': cutoff, 'confirmation': 'DELETE', 'organization_id': str(uuid.uuid4())}):
        assert (await client.request('DELETE', '/api/admin/audit-log', headers=auth_headers, json=body)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize('cutoff', ['not-a-date', '2020-01-01T00:00:00',
                                  (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()])
async def test_cleanup_rejects_invalid_or_ambiguous_cutoffs(client, auth_headers, cutoff):
    assert (await client.post('/api/admin/audit-log/cleanup-preview', headers=auth_headers,
                              json={'before': cutoff})).status_code == 422
    assert (await client.request('DELETE', '/api/admin/audit-log', headers=auth_headers,
                                 json={'before': cutoff, 'confirmation': 'DELETE'})).status_code == 422


@pytest.mark.asyncio
async def test_cleanup_rolls_back_if_audit_record_cannot_be_written(client, sessions, auth_headers, history):
    cutoff, _, _ = history
    with patch('app.services.activity_service.ActivityService.log', side_effect=RuntimeError('audit unavailable')):
        with pytest.raises(RuntimeError, match='audit unavailable'):
            await client.request('DELETE', '/api/admin/audit-log', headers=auth_headers,
                                 json={'before': cutoff, 'confirmation': 'DELETE'})
    async with sessions() as db:
        assert len((await db.scalars(select(ActivityEvent))).all()) == 6
