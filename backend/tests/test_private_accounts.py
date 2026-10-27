"""Private workspaces and account deletion using isolated, unpaid test data."""
import uuid
import pytest
from sqlalchemy import select
from app.models import Project, SearchJob, NormalizedPost, User
from app.models.export_job import ExportJob
from app.models.feedback import Feedback
from app.models.activity_event import ActivityEvent
from tests.test_pilot_accounts import add_user, headers, PASSWORD


@pytest.mark.asyncio
async def test_new_accounts_start_empty_and_cannot_access_other_projects(client, sessions, seed_org_and_user, auth_headers):
    org, admin, _ = seed_org_and_user
    member = await add_user(sessions, org)
    second = await add_user(sessions, org)
    admin_project = (await client.post('/api/projects', headers=auth_headers, json={'name': 'Admin project'})).json()
    assert (await client.get('/api/projects', headers=headers(member))).json() == []
    dashboard = (await client.get('/api/dashboard/summary', headers=headers(member))).json()
    assert dashboard['kpis'] == {'total_projects': 0, 'total_posts': 0, 'active_jobs': 0}
    assert dashboard['recent_projects'] == [] and dashboard['active_jobs'] == []
    own = (await client.post('/api/projects', headers=headers(member), json={
        'name': 'Member project', 'owner_user_id': str(admin.id), 'organization_id': str(uuid.uuid4())})).json()
    assert [p['id'] for p in (await client.get('/api/projects', headers=headers(member))).json()] == [own['id']]
    assert [p['id'] for p in (await client.get('/api/projects', headers=auth_headers)).json()] == [admin_project['id']]
    assert (await client.get('/api/projects', headers=headers(second))).json() == []
    async with sessions() as db:
        saved = await db.get(Project, uuid.UUID(own['id']))
        assert saved.owner_user_id == member.id and saved.organization_id == org.id
        job = SearchJob(project_id=saved.id, name='Private job', platforms=['reddit'], status='queued')
        post = NormalizedPost(project_id=saved.id, platform='reddit', vendor='test', external_id='private')
        export = ExportJob(project_id=saved.id, format='csv', status='completed')
        db.add_all([job, post, export])
        await db.commit()
    base = f"/api/projects/{own['id']}"
    attempts = [
        ('GET', base, None), ('PATCH', base, {'name': 'Intrusion'}), ('DELETE', base, None),
        ('GET', base+'/posts', None), ('PATCH', base+f'/posts/{post.id}/exclusion', {'excluded': True}),
        ('GET', base+'/jobs', None), ('GET', base+f'/jobs/{job.id}', None),
        ('POST', base+'/jobs', {'name': 'Bad', 'query': 'test', 'platforms': ['reddit'], 'requested_post_count': 100}),
        ('POST', base+f'/jobs/{job.id}/cancel', None),
        ('GET', base+'/analytics/overview', None), ('GET', base+'/analytics/volume', None),
        ('GET', base+'/analytics/engagement', None), ('GET', base+'/analytics/platforms', None),
        ('GET', base+'/analytics/wordmap', None), ('GET', base+'/exports', None),
        ('POST', base+'/exports', {'format': 'csv'}), ('GET', base+f'/exports/{export.id}/download', None),
    ]
    # Even another admin's role does not bypass project ownership in normal research routes.
    for caller in (headers(second), auth_headers):
        for method, path, body in attempts:
            response = await client.request(method, path, headers=caller, json=body)
            assert response.status_code == 404, (method, path, response.text)
        assert (await client.get('/api/dashboard/summary', headers=caller)).json()['kpis']['active_jobs'] == 0
    assert (await client.get(base, headers=headers(member))).status_code == 200
    assert (await client.get('/api/dashboard/summary', headers=headers(member))).json()['kpis']['active_jobs'] == 1
    events = (await client.get('/api/admin/audit-log', headers=auth_headers, params={'user_id': str(member.id)})).json()
    assert any(e['action'] == 'project_created' and e['target_label'] == 'Member project' for e in events)


@pytest.mark.asyncio
async def test_legacy_unassigned_projects_remain_admin_only(client, sessions, seed_org_and_user, auth_headers):
    org, _, _ = seed_org_and_user
    member = await add_user(sessions, org)
    async with sessions() as db:
        legacy = Project(organization_id=org.id, name='Legacy data')
        db.add(legacy)
        await db.commit()
    assert (await client.get(f'/api/projects/{legacy.id}', headers=auth_headers)).status_code == 200
    assert (await client.get(f'/api/projects/{legacy.id}', headers=headers(member))).status_code == 404
    assert (await client.get('/api/projects', headers=headers(member))).json() == []


@pytest.mark.asyncio
async def test_delete_member_preserves_history_and_revokes_access(client, sessions, seed_org_and_user, auth_headers):
    org, _, _ = seed_org_and_user
    member = await add_user(sessions, org)
    token = headers(member)
    project = (await client.post('/api/projects', headers=token, json={'name': 'Retained research'})).json()
    report = (await client.post('/api/feedback', headers=token,
        json={'kind': 'issue', 'message': 'Please help', 'page_path': '/projects', 'error_details': 'Exact error\n  at line 2'})).json()
    async with sessions() as db:
        job = SearchJob(project_id=uuid.UUID(project['id']), name='Completed run', platforms=['reddit'],
            status='completed', initiated_by=member.id, initiator_label=member.email, cancel_requested_by=member.id)
        db.add(job)
        await db.commit()
    response = await client.delete(f'/api/admin/users/{member.id}', headers=auth_headers)
    assert response.status_code == 204
    assert (await client.get('/api/auth/me', headers=token)).status_code == 401
    async with sessions() as db:
        assert await db.get(User, member.id) is None
        retained = await db.get(Project, uuid.UUID(project['id']))
        assert retained is not None and retained.owner_user_id is None
        report_row = await db.get(Feedback, uuid.UUID(report['id']))
        assert report_row.user_id is None and report_row.submitter_label == member.email
        assert report_row.error_details == 'Exact error\n  at line 2'
        job_row = await db.get(SearchJob, job.id)
        assert job_row.initiated_by is None and job_row.initiator_label == member.email
        assert job_row.cancel_requested_by is None
        history = (await db.scalars(select(ActivityEvent).where(ActivityEvent.actor_label == member.email))).all()
        assert history and all(event.actor_user_id is None for event in history)
    # Reusing an email creates a new identity and does not inherit deleted-account projects.
    recreated = await client.post('/api/admin/users', headers=auth_headers,
        json={'full_name': 'Replacement', 'email': member.email, 'password': PASSWORD})
    assert recreated.status_code == 201 and recreated.json()['id'] != str(member.id)
    login = (await client.post('/api/auth/login', json={'email': member.email, 'password': PASSWORD})).json()
    assert (await client.get('/api/projects', headers={'Authorization': 'Bearer '+login['access_token']})).json() == []
    assert (await client.get(f"/api/projects/{project['id']}", headers=auth_headers)).status_code == 200
    assert any(e['action'] == 'account_deleted' for e in (await client.get('/api/admin/audit-log', headers=auth_headers)).json())


@pytest.mark.asyncio
async def test_delete_rejects_admins_non_admins_other_organizations_and_active_jobs(client, sessions, seed_org_and_user, auth_headers):
    org, admin, _ = seed_org_and_user
    member = await add_user(sessions, org)
    other_member = await add_user(sessions)
    second_admin = await add_user(sessions, org, role='admin')
    for account in (admin, second_admin):
        assert (await client.delete(f'/api/admin/users/{account.id}', headers=auth_headers)).status_code == 409
    assert (await client.delete(f'/api/admin/users/{other_member.id}', headers=auth_headers)).status_code == 404
    assert (await client.delete(f'/api/admin/users/{member.id}', headers=headers(member))).status_code == 403
    assert (await client.delete(f'/api/admin/users/{member.id}')).status_code in (401, 403)
    async with sessions() as db:
        project = Project(organization_id=org.id, owner_user_id=member.id, name='Busy project')
        db.add(project)
        await db.flush()
        job = SearchJob(project_id=project.id, name='Busy run', platforms=['reddit'], status='running')
        db.add(job)
        await db.commit()
    assert (await client.delete(f'/api/admin/users/{member.id}', headers=auth_headers)).status_code == 409
    async with sessions() as db:
        job_row = await db.get(SearchJob, job.id)
        job_row.status = 'completed'
        await db.commit()
    assert (await client.delete(f'/api/admin/users/{member.id}', headers=auth_headers)).status_code == 204


@pytest.mark.asyncio
async def test_feedback_preserves_multiline_errors_and_admin_only_access(client, sessions, seed_org_and_user, auth_headers):
    org, _, _ = seed_org_and_user
    member = await add_user(sessions, org)
    other_admin = await add_user(sessions, role='admin')
    error = 'TypeError: <script>not executed</script>\n  at results.tsx:42\n    expected 1, got 0\n'
    body = {'kind': 'issue', 'message': 'Results failed', 'page_path': '/projects?secret=omit', 'error_details': error}
    assert (await client.post('/api/feedback', headers=headers(member), json=body)).status_code == 201
    report = (await client.get('/api/admin/feedback', headers=auth_headers)).json()[0]
    assert report['error_details'] == error and report['page_path'] == '/projects'
    assert (await client.get('/api/admin/feedback', headers=headers(other_admin))).json() == []
    assert (await client.get('/api/admin/feedback', headers=headers(member))).status_code == 403
    body['error_details'] = 'x' * 20001
    assert (await client.post('/api/feedback', headers=headers(member), json=body)).status_code == 422
