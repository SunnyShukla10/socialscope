"""Offline pilot checks; no live accounts, providers, or production database."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from sqlalchemy import select
from app.models import User, Organization, Project, SearchJob, NormalizedPost
from app.models.activity_event import ActivityEvent
from app.models.feedback import Feedback
from app.manage_users import ensure_admin
from app.services.auth_service import AuthService
from app.services.activity_service import ActivityService
from app.services.user_service import reset_password
from app.services.project_service import ProjectService
from app.services.abandoned_jobs import reconcile_abandoned_jobs
from app.models.export_job import ExportJob

PASSWORD = "temporary-test-password"


def headers(user):
    return {"Authorization": "Bearer " + AuthService(None).create_access_token(
        {"sub": str(user.id), "ver": user.token_version})}


async def add_user(sessions, org=None, role="member"):
    async with sessions() as db:
        if org is None:
            org = Organization(name="Other team", slug=str(uuid.uuid4()))
            db.add(org)
            await db.flush()
        user = User(organization_id=org.id, full_name="Another researcher", email=f"{uuid.uuid4()}@example.com",
            role=role, hashed_password=User.hash_password(PASSWORD))
        db.add(user)
        await db.commit()
        return user


@pytest.mark.asyncio
async def test_create_member_login_activity_and_duplicate(client, seed_org_and_user, auth_headers):
    body = {"full_name": "New Researcher", "email": " New@Example.com ", "password": PASSWORD}
    created = await client.post('/api/admin/users', json=body, headers=auth_headers)
    assert created.status_code == 201
    account = created.json()
    assert account['role'] == 'member' and account['email'] == 'new@example.com'
    assert not any('password' in key for key in account)
    login = await client.post('/api/auth/login', json={"email": "NEW@example.com", "password": PASSWORD})
    assert login.status_code == 200
    log = (await client.get('/api/admin/audit-log', headers=auth_headers,
        params={"user_id": account['id']})).json()
    assert [event['action'] for event in log] == ['login_succeeded']
    assert (await client.post('/api/admin/users', json=body, headers=auth_headers)).status_code == 409
    assert (await client.post('/api/admin/users', json={**body, 'role': 'admin'}, headers=auth_headers)).status_code == 422


@pytest.mark.asyncio
async def test_permissions_and_organization_isolation(client, sessions, seed_org_and_user, auth_headers):
    org, _, _ = seed_org_and_user
    member = await add_user(sessions, org)
    other_admin = await add_user(sessions, role='admin')
    for path in ('/api/admin/users', '/api/admin/audit-log', '/api/admin/feedback', '/api/admin/overview'):
        assert (await client.get(path, headers=headers(member))).status_code == 403
        assert (await client.get(path)).status_code in (401, 403)
    assert (await client.post('/api/admin/users', headers=headers(member), json={
        'full_name': 'Bad', 'email': 'bad@example.com', 'password': PASSWORD})).status_code == 403
    assert (await client.patch(f'/api/admin/users/{member.id}', headers=headers(member), json={'is_active': False})).status_code == 403
    listing = (await client.get('/api/admin/users', headers=auth_headers)).json()
    assert str(other_admin.id) not in {u['id'] for u in listing}
    assert (await client.patch(f'/api/admin/users/{other_admin.id}', headers=auth_headers, json={'is_active': False})).status_code == 404
    await client.post('/api/feedback', headers=headers(other_admin), json={'kind': 'issue', 'message': 'Other team', 'page_path': '/projects'})
    assert (await client.get('/api/admin/feedback', headers=auth_headers)).json() == []


@pytest.mark.asyncio
async def test_disable_revokes_tokens_and_last_admin_protected(client, sessions, seed_org_and_user, auth_headers):
    org, admin, _ = seed_org_and_user
    member = await add_user(sessions, org)
    token = headers(member)
    assert (await client.patch(f'/api/admin/users/{admin.id}', headers=auth_headers, json={'is_active': False})).status_code == 409
    assert (await client.patch(f'/api/admin/users/{member.id}', headers=auth_headers, json={'is_active': False})).status_code == 200
    assert (await client.get('/api/auth/me', headers=token)).status_code == 401
    assert (await client.post('/api/auth/login', json={'email': member.email, 'password': PASSWORD})).status_code == 401
    assert (await client.patch(f'/api/admin/users/{member.id}', headers=auth_headers, json={'is_active': True})).status_code == 200
    assert (await client.get('/api/auth/me', headers=token)).status_code == 401
    assert (await client.post('/api/auth/login', json={'email': member.email, 'password': PASSWORD})).status_code == 200


@pytest.mark.asyncio
async def test_feedback_validation_review_and_privacy(client, sessions, seed_org_and_user, auth_headers):
    org, _, _ = seed_org_and_user
    member = await add_user(sessions, org)
    other_admin = await add_user(sessions, role='admin')
    body = {'kind': 'issue', 'message': 'Chart did not load', 'page_path': '/projects?token=private#secret'}
    response = await client.post('/api/feedback', headers=headers(member), json=body)
    assert response.status_code == 201
    report_id = response.json()['id']
    async with sessions() as db:
        saved = await db.get(Feedback, uuid.UUID(report_id))
        assert saved.user_id == member.id and saved.page_path == '/projects'
    for invalid in ({**body, 'message': '   '}, {**body, 'kind': 'other'}, {**body, 'page_path': '//outside.com'}, {**body, 'organization_id': str(org.id)}):
        assert (await client.post('/api/feedback', headers=headers(member), json=invalid)).status_code == 422
    assert (await client.post('/api/feedback', json=body)).status_code in (401, 403)
    assert (await client.get('/api/feedback', headers=headers(member))).status_code == 405
    review_path = f'/api/admin/feedback/{report_id}'
    assert (await client.patch(review_path, headers=headers(member), json={'reviewed': True})).status_code == 403
    assert (await client.patch(review_path, headers=headers(other_admin), json={'reviewed': True})).status_code == 404
    assert (await client.patch(review_path, headers=auth_headers, json={'reviewed': True})).json()['reviewed'] is True
    assert (await client.get('/api/admin/feedback', headers=auth_headers)).json()[0]['reviewed'] is True


@pytest.mark.asyncio
async def test_seed_preserves_existing_account_and_password_reset(client, sessions, seed_org_and_user):
    org, user, original_password = seed_org_and_user
    original_token = headers(user)
    async with sessions() as db:
        existing, created = await ensure_admin(db, email=user.email.upper(), password=PASSWORD,
            full_name='Overwrite attempt', organization_slug='different')
        assert not created
        assert existing.organization_id == org.id and existing.full_name == user.full_name
        assert existing.role == user.role and existing.verify_password(original_password)
        await reset_password(db, existing, PASSWORD)
        await db.commit()
    assert (await client.get('/api/auth/me', headers=original_token)).status_code == 401
    assert (await client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})).status_code == 200


@pytest.mark.asyncio
async def test_seed_does_not_promote_or_reenable_member(sessions, seed_org_and_user):
    org, _, _ = seed_org_and_user
    member = await add_user(sessions, org)
    async with sessions() as db:
        saved = await db.get(User, member.id)
        saved.is_active = False
        await db.commit()
        found, created = await ensure_admin(db, email=member.email, password=PASSWORD)
        assert not created and found.role == 'member' and not found.is_active
        admin, created = await ensure_admin(db, email='fresh-admin@example.com', password=PASSWORD)
        assert created and admin.role == 'admin'


@pytest.mark.asyncio
async def test_activity_filter_pagination_and_history_survives_delete(client, sessions, seed_org_and_user, auth_headers):
    org, admin, _ = seed_org_and_user
    project = (await client.post('/api/projects', headers=auth_headers, json={'name': 'History project'})).json()
    assert (await client.delete(f"/api/projects/{project['id']}", headers=auth_headers)).status_code == 204
    events = (await client.get('/api/admin/audit-log', headers=auth_headers, params={'user_id': str(admin.id)})).json()
    assert {e['action'] for e in events} == {'project_created', 'project_deleted'}
    assert all(e['target_label'] == 'History project' for e in events)
    assert all(e['project_id'] is None for e in events)
    first = (await client.get('/api/admin/audit-log?limit=1', headers=auth_headers)).json()
    second = (await client.get('/api/admin/audit-log?limit=1&offset=1', headers=auth_headers)).json()
    assert first[0]['id'] != second[0]['id']
    assert (await client.get('/api/admin/audit-log?limit=251', headers=auth_headers)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['completed', 'completed_with_errors', 'failed', 'cancelled'])
async def test_background_outcome_attribution_and_idempotency(sessions, seed_org_and_user, outcome):
    org, user, _ = seed_org_and_user
    async with sessions() as db:
        project = Project(name='Collection project', organization_id=org.id)
        db.add(project)
        await db.flush()
        job = SearchJob(project_id=project.id, name='Run', platforms=['reddit'], status=outcome,
            initiated_by=user.id, initiator_label=user.email)
        db.add(job)
        await db.flush()
        await ActivityService(db).collection_outcome(job)
        await db.commit()
        await ActivityService(db).collection_outcome(job)
        await db.commit()
        events = (await db.scalars(select(ActivityEvent))).all()
        assert len(events) == 1
        assert events[0].actor_user_id == user.id and events[0].actor_label == user.email
        assert events[0].extra_metadata['outcome'] == outcome


@pytest.mark.asyncio
async def test_abandoned_legacy_job_is_unknown(sessions, seed_org_and_user):
    org, _, _ = seed_org_and_user
    now = datetime.now(timezone.utc)
    async with sessions() as db:
        project = Project(name='Legacy project', organization_id=org.id)
        db.add(project)
        await db.flush()
        job = SearchJob(project_id=project.id, name='Legacy run', platforms=['reddit'],
            status='running', last_progress_at=now - timedelta(hours=2))
        db.add(job)
        await db.commit()
        await reconcile_abandoned_jobs(db, stale_before=now-timedelta(hours=1), recovered_at=now,
            batch_size=10, active_task_ids=set())
        event = await db.scalar(select(ActivityEvent))
        assert event.actor_user_id is None and event.actor_label == 'System / Unknown'


@pytest.mark.asyncio
async def test_collection_submission_retains_initiator(client, sessions, seed_org_and_user, auth_headers):
    _, user, _ = seed_org_and_user
    project = (await client.post('/api/projects', headers=auth_headers, json={'name': 'Attributed project'})).json()
    with patch('app.workers.tasks.run_collection_job.apply_async'):
        response = await client.post(f"/api/projects/{project['id']}/jobs", headers=auth_headers,
            json={'name': 'Run', 'query': 'public transit', 'platforms': ['reddit'], 'requested_post_count': 100})
    assert response.status_code == 201
    async with sessions() as db:
        job = await db.get(SearchJob, uuid.UUID(response.json()['id']))
        assert job.initiated_by == user.id and job.initiator_label == user.email


@pytest.mark.asyncio
async def test_exclusion_and_download_audit_without_post_content(client, sessions, seed_org_and_user, auth_headers, tmp_path):
    org, user, _ = seed_org_and_user
    export_file = tmp_path / 'report.csv'
    export_file.write_text('id\n1\n')
    async with sessions() as db:
        project = Project(name='Audit project', organization_id=org.id)
        db.add(project)
        await db.flush()
        post = NormalizedPost(project_id=project.id, platform='reddit', vendor='test', external_id='one', body='Do not copy private content into audit')
        export = ExportJob(project_id=project.id, format='csv', status='completed', file_path=str(export_file))
        db.add_all([post, export])
        await db.commit()
    path = f'/api/projects/{project.id}/posts/{post.id}/exclusion'
    assert (await client.patch(path, headers=auth_headers, json={'excluded': True})).status_code == 200
    assert (await client.patch(path, headers=auth_headers, json={'excluded': True})).status_code == 200
    assert (await client.patch(path, headers=auth_headers, json={'excluded': False})).status_code == 200
    download = await client.get(f'/api/projects/{project.id}/exports/{export.id}/download', headers=auth_headers)
    assert download.status_code == 200
    events = (await client.get('/api/admin/audit-log', headers=auth_headers)).json()
    assert [e['action'] for e in events].count('post_excluded') == 1
    assert {e['action'] for e in events} == {'post_excluded', 'post_restored', 'export_download_requested'}
    assert all(e['actor_user_id'] == str(user.id) for e in events)
    assert 'Do not copy private content' not in str(events)
    assert next(e for e in events if e['action'] == 'export_download_requested')['extra_metadata']['outcome'] == 'requested'


@pytest.mark.asyncio
async def test_dispatch_failure_is_attributed(client, sessions, seed_org_and_user, auth_headers):
    _, user, _ = seed_org_and_user
    project = (await client.post('/api/projects', headers=auth_headers, json={'name': 'Queue failure'})).json()
    with patch('app.workers.tasks.run_collection_job.apply_async', side_effect=RuntimeError('offline broker')):
        response = await client.post(f"/api/projects/{project['id']}/jobs", headers=auth_headers,
            json={'name': 'Run', 'query': 'public transit', 'platforms': ['reddit'], 'requested_post_count': 100})
    assert response.status_code == 201 and response.json()['status'] == 'failed'
    events = (await client.get('/api/admin/audit-log', headers=auth_headers)).json()
    failed = next(e for e in events if e['action'] == 'collection_failed')
    assert failed['actor_user_id'] == str(user.id) and failed['extra_metadata']['outcome'] == 'failed'
