'use client'

import React, { useEffect, useState } from 'react'
import { fetchApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Eye, EyeOff } from 'lucide-react'

type Account = { id: string; full_name: string; email: string; role: string; is_active: boolean }
type Activity = {
  id: string; actor_label: string; action: string; target_label?: string; target_type: string
  target_id?: string; created_at: string; extra_metadata: { outcome?: string; mode?: string }
}
type Report = { id: string; submitter_label: string; kind: string; message: string; error_details?: string | null; page_path: string; created_at: string; reviewed: boolean }
const pageSize = 25
const sectionClass = 'bg-surface border border-border rounded-xl p-6 space-y-4'
const inputClass = 'rounded border border-border bg-background p-2 text-sm text-text'
const errorMessage = (err: unknown) => (err as { message?: string }).message || 'Could not save changes. Please try again.'
const actionLabel = (action: string) => action === 'collection_pull_started' ? 'Collection submitted' : action.replaceAll('_', ' ')

function Pages({ page, count, busy, setPage }: { page: number; count: number; busy: boolean; setPage: (value: number) => void }) {
  return <div className="flex items-center gap-3 text-sm text-text-muted">
    <Button type="button" variant="outline" disabled={busy || page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
    <span>Page {page + 1}</span>
    <Button type="button" variant="outline" disabled={busy || count < pageSize} onClick={() => setPage(page + 1)}>Next</Button>
  </div>
}

export function PilotAdmin() {
  const [users, setUsers] = useState<Account[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [userPage, setUserPage] = useState(0)
  const [activityPage, setActivityPage] = useState(0)
  const [reportPage, setReportPage] = useState(0)
  const [filter, setFilter] = useState('')
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([
      fetchApi<Account[]>(`/admin/users?limit=${pageSize}&offset=${userPage * pageSize}`),
      fetchApi<Activity[]>(`/admin/audit-log?limit=${pageSize}&offset=${activityPage * pageSize}${filter ? `&user_id=${filter}` : ''}`),
      fetchApi<Report[]>(`/admin/feedback?limit=${pageSize}&offset=${reportPage * pageSize}`),
    ]).then(([u, a, r]) => { if (active) { setUsers(u); setActivity(a); setReports(r) } })
      .catch(err => { if (active) setError(errorMessage(err)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userPage, activityPage, reportPage, filter, reload])

  async function mutate(path: string, method: string, body: unknown, success: string): Promise<boolean> {
    setBusy(true); setError(''); setNotice('')
    try {
      await fetchApi(path, { method, body: JSON.stringify(body) })
      setReload(value => value + 1); setNotice(success)
      return true
    } catch (err) { setError(errorMessage(err)); return false }
    finally { setBusy(false) }
  }

  return <>
    <div className="flex items-center justify-between gap-3">
      <p className="text-sm text-text-muted">Accounts, activity, and feedback for your organization.</p>
      <Button variant="outline" disabled={loading || busy} onClick={() => setReload(value => value + 1)}>Refresh</Button>
    </div>
    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    {notice && <p role="status" className="text-sm text-text">{notice}</p>}
    {loading && <p role="status" className="text-sm text-text-muted">Loading admin records…</p>}

    <section className={sectionClass}>
      <h2 className="text-base font-semibold text-text">Users</h2>
      <p className="text-sm text-text-muted">Each account starts with its own projects. Admin activity oversight stays available here.</p>
      <form className="flex flex-wrap items-end gap-3" onSubmit={async event => {
        event.preventDefault()
        if (await mutate('/admin/users', 'POST', { full_name: name, email, password }, 'Member account created.')) {
          setName(''); setEmail(''); setPassword(''); setShowPassword(false); setUserPage(0)
        }
      }}>
        <label className="text-sm text-text">Name<input required maxLength={255} value={name} onChange={e => setName(e.target.value)} className={`block mt-1 ${inputClass}`} /></label>
        <label className="text-sm text-text">Email<input required type="email" maxLength={255} value={email} onChange={e => setEmail(e.target.value)} className={`block mt-1 ${inputClass}`} /></label>
        <div className="text-sm text-text">
          <label htmlFor="new-member-password">Password</label>
          <div className="relative mt-1">
            <input id="new-member-password" required type={showPassword ? 'text' : 'password'} autoComplete="new-password"
              minLength={12} value={password} onChange={e => setPassword(e.target.value)} className={`${inputClass} pr-10`} />
            <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
              onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword} aria-controls="new-member-password">
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>
        <Button type="submit" disabled={busy || loading}>Create member</Button>
      </form>
      <p className="text-xs text-text-muted">Passwords require at least 12 characters and at most 72 UTF-8 bytes. Share credentials privately through an encrypted channel.</p>
      <div className="overflow-x-auto"><table className="w-full text-sm text-left text-text">
        <thead><tr className="border-b border-border"><th className="p-2">Name</th><th className="p-2">Email</th><th className="p-2">Role</th><th className="p-2">Status</th><th className="p-2">Access</th></tr></thead>
        <tbody>{users.map(user => <tr key={user.id} className="border-b border-border">
          <td className="p-2">{user.full_name}</td><td className="p-2"><button className="text-primary underline" onClick={() => { setFilter(user.id); setActivityPage(0) }} title="Show this person's activity">{user.email}</button></td>
          <td className="p-2">{user.role}</td><td className="p-2">{user.is_active ? 'Active' : 'Disabled'}</td>
          <td className="p-2"><Button variant="outline" disabled={busy || loading} onClick={() => {
            if (user.is_active && !window.confirm(`Disable access for ${user.email}?`)) return
            void mutate(`/admin/users/${user.id}`, 'PATCH', { is_active: !user.is_active }, 'Account access updated.')
          }}>{user.is_active ? 'Disable' : 'Enable'}</Button>
            {user.role !== 'admin' && <Button variant="outline" className="ml-2 text-red-600" disabled={busy || loading} onClick={async () => {
              if (!window.confirm(`Delete the account for ${user.email}? Access will be removed permanently. Research data and history will be retained for administrators.`)) return
              if (await mutate(`/admin/users/${user.id}`, 'DELETE', undefined, 'Member account deleted. Research data and history retained.')) {
                if (filter === user.id) { setFilter(''); setActivityPage(0) }
                setUserPage(0)
              }
            }}>Delete</Button>}
          </td>
        </tr>)}</tbody>
      </table></div>
      {!users.length && !loading && <p className="text-sm text-text-muted">No users on this page.</p>}
      <Pages page={userPage} count={users.length} busy={loading || busy} setPage={setUserPage} />
    </section>

    <section className={sectionClass}>
      <h2 className="text-base font-semibold text-text">User activity</h2>
      <p className="text-sm text-text-muted">Logins, project changes, collection outcomes, dataset decisions, and export requests.</p>
      <label className="block text-sm text-text">Filter by person
        <select value={filter} className={`ml-3 ${inputClass}`} onChange={e => { setFilter(e.target.value); setActivityPage(0) }}>
          <option value="">All users / System</option>
          {filter && !users.some(u => u.id === filter) && <option value={filter}>Selected user</option>}
          {users.map(user => <option key={user.id} value={user.id}>{user.email}</option>)}
        </select>
      </label>
      <p className="text-xs text-text-muted">Choose from the current Users page, or click a person's email above. Older unattributed events remain System / Unknown.</p>
      <div className="overflow-x-auto"><table className="w-full text-sm text-left text-text">
        <thead><tr className="border-b border-border"><th className="p-2">Time</th><th className="p-2">User</th><th className="p-2">Action</th><th className="p-2">Project / target</th><th className="p-2">Outcome</th></tr></thead>
        <tbody>{activity.map(event => <tr key={event.id} className="border-b border-border">
          <td className="p-2 whitespace-nowrap">{new Date(event.created_at).toLocaleString()}</td><td className="p-2">{event.actor_label}</td>
          <td className="p-2">{actionLabel(event.action)}{event.extra_metadata.mode && <span className="block text-xs text-text-muted">{event.extra_metadata.mode}</span>}</td>
          <td className="p-2" title={event.target_id}>{event.target_label || event.target_type}</td>
          <td className="p-2">{event.extra_metadata.outcome?.replaceAll('_', ' ') || '—'}</td>
        </tr>)}</tbody>
      </table></div>
      {!activity.length && !loading && <p className="text-sm text-text-muted">No activity matches this page and filter.</p>}
      <Pages page={activityPage} count={activity.length} busy={loading || busy} setPage={setActivityPage} />
    </section>

    <section className={sectionClass}>
      <h2 className="text-base font-semibold text-text">Feedback &amp; issues</h2>
      {reports.map(report => <article key={report.id} className="border border-border rounded-lg p-4 space-y-2 text-sm text-text">
        <p><strong>{report.kind === 'issue' ? 'Issue' : 'Feedback'}</strong> · {report.submitter_label} · {new Date(report.created_at).toLocaleString()}</p>
        <p className="text-xs text-text-muted break-all">{report.page_path}</p>
        <p className="whitespace-pre-wrap break-words">{report.message}</p>
        {report.error_details && <div><p className="font-medium mb-1">Pasted error details</p>
          <pre className="whitespace-pre-wrap break-words overflow-x-auto max-h-80 overflow-y-auto rounded border border-border bg-background p-3 text-xs font-mono">{report.error_details}</pre>
        </div>}
        <label className="flex items-center gap-2"><input type="checkbox" checked={report.reviewed} disabled={busy || loading}
          onChange={e => { void mutate(`/admin/feedback/${report.id}`, 'PATCH', { reviewed: e.target.checked }, 'Review status saved.') }} />Reviewed</label>
      </article>)}
      {!reports.length && !loading && <p className="text-sm text-text-muted">No feedback on this page.</p>}
      <Pages page={reportPage} count={reports.length} busy={loading || busy} setPage={setReportPage} />
    </section>
  </>
}
