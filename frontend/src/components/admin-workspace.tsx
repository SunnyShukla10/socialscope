'use client'

import React, { useEffect, useState } from 'react'
import { fetchApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Activity as ActivityIcon, Eye, EyeOff, MessageSquare, Plus, RefreshCw, Trash2, Users } from 'lucide-react'

type Account = { id: string; full_name: string; email: string; role: string; is_active: boolean }
type Activity = {
  id: string; actor_label: string; action: string; target_label?: string; target_type: string
  target_id?: string; created_at: string; extra_metadata: { outcome?: string; mode?: string; deleted_count?: number; before?: string }
}
type Report = { id: string; submitter_label: string; kind: string; message: string; error_details?: string | null; page_path: string; created_at: string; reviewed: boolean }
const pageSize = 25
type CleanupPreview = { before: string; user_id: string | null; matching_count: number }
const sectionClass = 'min-w-0 bg-surface border border-border rounded-xl p-4 sm:p-5 space-y-4 shadow-card'
const inputClass = 'rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20'
const errorMessage = (err: unknown) => (err as { message?: string }).message || 'Could not save changes. Please try again.'
const actionLabel = (action: string) => action === 'collection_pull_started' ? 'Collection submitted' : action.replaceAll('_', ' ')

function Pages({ page, count, busy, setPage }: { page: number; count: number; busy: boolean; setPage: (value: number) => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3 text-xs text-text-muted">
    <span>Page {page + 1} · {count} records shown</span>
    <div className="flex gap-2">
      <Button type="button" size="sm" variant="outline" disabled={busy || page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
      <Button type="button" size="sm" variant="outline" disabled={busy || count < pageSize} onClick={() => setPage(page + 1)}>Next</Button>
    </div>
  </div>
}

export function AdminWorkspace() {
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
  const [section, setSection] = useState<'activity' | 'users' | 'feedback'>('activity')
  const [createOpen, setCreateOpen] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [filterLabel, setFilterLabel] = useState('All users / System')
  const [retentionDays, setRetentionDays] = useState('90')
  const [cleanupOpen, setCleanupOpen] = useState(false)
  const [preview, setPreview] = useState<CleanupPreview | null>(null)
  const [confirmed, setConfirmed] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([
      fetchApi<Account[]>(`/admin/users?limit=${pageSize}&offset=${userPage * pageSize}`),
      fetchApi<Activity[]>(`/admin/audit-log?limit=${pageSize}&offset=${activityPage * pageSize}${filter ? `&user_id=${filter}` : ''}`),
      fetchApi<Report[]>(`/admin/feedback?limit=${pageSize}&offset=${reportPage * pageSize}`),
    ]).then(([u, a, r]) => { if (active) { setUsers(u); setActivity(a); setReports(r); setUpdatedAt(new Date()) } })
      .catch(err => { if (active) setError(errorMessage(err)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userPage, activityPage, reportPage, filter, reload])

  async function mutate(path: string, method: string, body: unknown, success: string): Promise<boolean> {
    setBusy(true); setError(''); setNotice('')
    try {
      await fetchApi(path, { method, body: body === undefined ? undefined : JSON.stringify(body) })
      setReload(value => value + 1); setNotice(success)
      return true
    } catch (err) { setError(errorMessage(err)); return false }
    finally { setBusy(false) }
  }

  function closeCreate() {
    if (busy) return
    setCreateOpen(false); setName(''); setEmail(''); setPassword(''); setShowPassword(false); setError('')
  }

  async function previewCleanup() {
    setCleanupOpen(true); setPreview(null); setConfirmed(false); setBusy(true); setError(''); setNotice('')
    const before = new Date(Date.now() - Number(retentionDays) * 86400000).toISOString()
    try {
      setPreview(await fetchApi<CleanupPreview>('/admin/audit-log/cleanup-preview', {
        method: 'POST', body: JSON.stringify({ before, user_id: filter || null }),
      }))
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  async function deleteActivity() {
    if (!preview || !confirmed || busy) return
    setBusy(true); setError('')
    try {
      const result = await fetchApi<{ deleted_count: number }>('/admin/audit-log', {
        method: 'DELETE', body: JSON.stringify({ before: preview.before, user_id: preview.user_id, confirmation: 'DELETE' }),
      })
      setCleanupOpen(false); setPreview(null); setConfirmed(false); setActivityPage(0)
      setNotice(`${result.deleted_count} older activity records deleted. A cleanup entry was added to activity.`)
      setReload(value => value + 1)
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  return <>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-lg font-semibold text-text">Organization workspace</h2>
        <p className="mt-1 text-xs text-text-muted">{updatedAt ? `Records updated ${updatedAt.toLocaleTimeString()}` : 'Accounts, activity, and feedback for your organization.'}</p>
      </div>
      <Button size="sm" variant="outline" disabled={loading || busy} onClick={() => { setNotice(''); setReload(value => value + 1) }}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden="true" />Refresh records</Button>
    </div>
    {error && !createOpen && !cleanupOpen && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-primary">{notice}</p>}
    {loading && <p role="status" className="text-sm text-text-muted">Loading admin records…</p>}

    <nav aria-label="Admin sections" className="flex gap-1 overflow-x-auto rounded-xl border border-border bg-background p-1.5">
      {([{ id: 'activity', label: 'Activity', icon: ActivityIcon }, { id: 'users', label: 'Users', icon: Users }, { id: 'feedback', label: 'Feedback & issues', icon: MessageSquare }] as const).map(({ id, label, icon: Icon }) =>
        <button type="button" key={id} aria-pressed={section === id} onClick={() => setSection(id)} className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${section === id ? 'bg-surface text-primary shadow-sm ring-1 ring-border' : 'text-text-muted hover:bg-surface hover:text-text'}`}><Icon size={16} aria-hidden="true" />{label}</button>)}
    </nav>

    <section hidden={section !== 'users'} className={sectionClass} aria-busy={loading}>
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-text">User access</h2><p className="mt-1 text-xs text-text-muted">Individual accounts with private projects.</p></div>
        <Button size="sm" disabled={loading || busy} onClick={() => { setError(''); setCreateOpen(true) }}><Plus size={15} aria-hidden="true" />Create user</Button>
      </div>
      <Dialog open={createOpen} onClose={closeCreate} title="Create user" description="Add a member to your organization.">
      <form onSubmit={async event => {
        event.preventDefault()
        if (busy) return
        if (await mutate('/admin/users', 'POST', { full_name: name, email, password }, 'Member account created.')) {
          setCreateOpen(false); setName(''); setEmail(''); setPassword(''); setShowPassword(false); setUserPage(0)
        }
      }}>
        <DialogContent className="space-y-4">
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <label className="block text-sm font-medium text-text">Full name<input data-dialog-autofocus required maxLength={255} autoComplete="name" disabled={busy} value={name} onChange={e => setName(e.target.value)} className={`block w-full mt-1 ${inputClass}`} /></label>
        <label className="block text-sm font-medium text-text">Email address<input required type="email" maxLength={255} autoComplete="off" disabled={busy} value={email} onChange={e => setEmail(e.target.value)} className={`block w-full mt-1 ${inputClass}`} /></label>
        <div className="text-sm text-text">
          <label htmlFor="new-member-password">Password</label>
          <div className="relative mt-1">
            <input id="new-member-password" required type={showPassword ? 'text' : 'password'} autoComplete="new-password"
              minLength={12} disabled={busy} value={password} onChange={e => setPassword(e.target.value)} className={`w-full ${inputClass} pr-12`} />
            <button type="button" disabled={busy} className="absolute right-2 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded text-text-muted hover:text-primary"
              onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword} aria-controls="new-member-password">
              {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
            </button>
          </div>
        </div>
        <p className="text-xs leading-relaxed text-text-muted">Use at least 12 characters and at most 72 UTF-8 bytes. Share credentials privately through an encrypted channel. No invitation email is sent.</p>
        </DialogContent>
        <DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={closeCreate}>Cancel</Button><Button type="submit" loading={busy}>Create user</Button></DialogFooter>
      </form>
      </Dialog>
      <div className="max-h-[60vh] overflow-auto rounded-lg border border-border"><table className="w-full text-sm text-left text-text">
        <thead className="sticky top-0 bg-background text-xs text-text-muted"><tr className="border-b border-border"><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Role</th><th className="p-3">Status</th><th className="p-3">Access</th></tr></thead>
        <tbody>{users.map(user => <tr key={user.id} className="border-b border-border/70 hover:bg-background/60">
          <td className="p-2 font-medium">{user.full_name}</td><td className="p-2"><button className="text-primary hover:underline" onClick={() => { setFilter(user.id); setFilterLabel(user.email); setActivityPage(0); setSection('activity') }} title="Show this person's activity">{user.email}</button></td>
          <td className="p-2"><Badge variant={user.role === 'admin' ? 'info' : 'muted'}>{user.role}</Badge></td><td className="p-2"><Badge variant={user.is_active ? 'success' : 'muted'}>{user.is_active ? 'Active' : 'Disabled'}</Badge></td>
          <td className="p-2 whitespace-nowrap"><Button size="sm" variant="outline" disabled={busy || loading} onClick={() => {
            if (user.is_active && !window.confirm(`Disable access for ${user.email}?`)) return
            void mutate(`/admin/users/${user.id}`, 'PATCH', { is_active: !user.is_active }, 'Account access updated.')
          }}>{user.is_active ? 'Disable' : 'Enable'}</Button>
            {user.role !== 'admin' && <Button size="sm" variant="ghost" className="ml-1 text-red-600 hover:bg-red-50" aria-label={`Delete account for ${user.email}`} disabled={busy || loading} onClick={async () => {
              if (!window.confirm(`Delete the account for ${user.email}? Access will be removed permanently. Research data and history will be retained for administrators.`)) return
              if (await mutate(`/admin/users/${user.id}`, 'DELETE', undefined, 'Member account deleted. Research data and history retained.')) {
                if (filter === user.id) { setFilter(''); setFilterLabel('All users / System'); setActivityPage(0) }
                setUserPage(0)
              }
            }}><Trash2 size={15} aria-hidden="true" /></Button>}
          </td>
        </tr>)}</tbody>
      </table></div>
      {!users.length && !loading && <p className="text-sm text-text-muted">No users on this page.</p>}
      <Pages page={userPage} count={users.length} busy={loading || busy} setPage={setUserPage} />
    </section>

    <section hidden={section !== 'activity'} className={sectionClass} aria-busy={loading}>
      <h2 className="text-base font-semibold text-text">User activity</h2>
      <p className="text-sm text-text-muted">Logins, project changes, collection outcomes, dataset decisions, and export requests.</p>
      <div className="flex flex-wrap items-end gap-3">
      <label className="block min-w-0 text-xs font-medium text-text">Person
        <select value={filter} disabled={busy || loading} className={`block mt-1 max-w-full ${inputClass}`} onChange={e => { setFilter(e.target.value); setFilterLabel(e.target.selectedOptions[0].text); setActivityPage(0) }}>
          <option value="">All users / System</option>
          {filter && !users.some(u => u.id === filter) && <option value={filter}>{filterLabel}</option>}
          {users.map(user => <option key={user.id} value={user.id}>{user.email}</option>)}
        </select>
      </label>
      <div className="flex flex-wrap items-end gap-2 sm:ml-auto">
        <label className="text-xs font-medium text-text">Cleanup age<select value={retentionDays} disabled={busy || loading} onChange={e => setRetentionDays(e.target.value)} className={`block mt-1 ${inputClass}`}>
          {[30, 90, 180, 365].map(days => <option key={days} value={days}>Older than {days} days</option>)}
        </select></label>
        <Button variant="outline" disabled={busy || loading} onClick={() => void previewCleanup()}><Trash2 size={14} aria-hidden="true" />Review cleanup</Button>
      </div>
      </div>
      <p className="text-xs text-text-muted">People come from the current Users page. Cleanup respects the person selected here; review the matching count before deleting.</p>
      <div className="max-h-[60vh] overflow-auto rounded-lg border border-border"><table className="w-full text-sm text-left text-text">
        <thead className="sticky top-0 bg-background text-xs text-text-muted"><tr className="border-b border-border"><th className="p-3">Time</th><th className="p-3">User</th><th className="p-3">Action</th><th className="p-3">Project / target</th><th className="p-3">Outcome</th></tr></thead>
        <tbody>{activity.map(event => <tr key={event.id} className="border-b border-border/70 hover:bg-background/60">
          <td className="p-2 whitespace-nowrap">{new Date(event.created_at).toLocaleString()}</td><td className="p-2">{event.actor_label}</td>
          <td className="p-2 capitalize">{actionLabel(event.action)}{event.extra_metadata.mode && <span className="block text-xs text-text-muted">{event.extra_metadata.mode}</span>}
            {event.action === 'activity_history_deleted' && <span className="block text-xs text-text-muted">{event.extra_metadata.deleted_count} records before {event.extra_metadata.before ? new Date(event.extra_metadata.before).toLocaleString() : 'selected cutoff'}</span>}
          </td>
          <td className="p-2" title={event.target_id}>{event.target_label || event.target_type}</td>
          <td className="p-2">{event.extra_metadata.outcome?.replaceAll('_', ' ') || '—'}</td>
        </tr>)}</tbody>
      </table></div>
      {!activity.length && !loading && <p className="text-sm text-text-muted">No activity matches this page and filter.</p>}
      <Pages page={activityPage} count={activity.length} busy={loading || busy} setPage={setActivityPage} />
    </section>

    <section hidden={section !== 'feedback'} className={sectionClass} aria-busy={loading}>
      <h2 className="text-base font-semibold text-text">Feedback &amp; issues</h2>
      {reports.map(report => <article key={report.id} className="border border-border rounded-lg p-4 space-y-2 text-sm text-text">
        <p><strong>{report.kind === 'issue' ? 'Issue' : 'Feedback'}</strong> · {report.submitter_label} · {new Date(report.created_at).toLocaleString()}</p>
        <p className="text-xs text-text-muted break-all">{report.page_path}</p>
        <p className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words">{report.message}</p>
        {report.error_details && <details className="rounded-lg bg-background p-3"><summary className="cursor-pointer text-xs font-medium">Pasted error details</summary>
          <pre className="whitespace-pre-wrap break-words overflow-x-auto max-h-80 overflow-y-auto rounded border border-border bg-background p-3 text-xs font-mono">{report.error_details}</pre>
        </details>}
        <label className="flex items-center gap-2"><input type="checkbox" checked={report.reviewed} disabled={busy || loading}
          onChange={e => { void mutate(`/admin/feedback/${report.id}`, 'PATCH', { reviewed: e.target.checked }, 'Review status saved.') }} />Reviewed</label>
      </article>)}
      {!reports.length && !loading && <p className="text-sm text-text-muted">No feedback on this page.</p>}
      <Pages page={reportPage} count={reports.length} busy={loading || busy} setPage={setReportPage} />
    </section>

    <Dialog open={cleanupOpen} onClose={() => { if (!busy) { setCleanupOpen(false); setError('') } }} title="Review activity cleanup" description="Permanently remove older activity entries." size="lg">
      <DialogContent className="space-y-4 text-sm text-text">
        {error && <p role="alert" className="text-red-700">{error}</p>}
        {busy && !preview && <p role="status">Counting matching records…</p>}
        {preview && <>
          <div className="rounded-xl border border-border bg-background p-4"><p className="text-3xl font-semibold tracking-tight">{preview.matching_count.toLocaleString()}</p><p className="mt-1 text-text-muted">matching activity records</p>
            <dl className="mt-4 space-y-2 text-xs"><div><dt className="text-text-muted">Person</dt><dd className="mt-1 break-words font-medium">{filterLabel}</dd></div><div><dt className="text-text-muted">Strictly before</dt><dd className="mt-1 font-medium">{new Date(preview.before).toLocaleString()} (your local time)</dd></div></dl>
          </div>
          <p className="text-xs leading-relaxed text-text-muted">Projects, posts, accounts, and feedback remain unchanged. This action cannot be undone. The count may change if another administrator cleans up records before you confirm.</p>
          {preview.matching_count > 0 ? <label className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"><input type="checkbox" checked={confirmed} disabled={busy} className="mt-1" onChange={e => setConfirmed(e.target.checked)} />I understand that matching activity will be permanently deleted.</label> : <p className="text-text-muted">Nothing to delete for this selection.</p>}
        </>}
      </DialogContent>
      <DialogFooter><Button variant="outline" disabled={busy} onClick={() => { setCleanupOpen(false); setError('') }}>Cancel</Button><Button variant="destructive" loading={busy && !!preview} disabled={!preview || !confirmed || preview.matching_count === 0 || busy} onClick={() => void deleteActivity()}>Delete older activity</Button></DialogFooter>
    </Dialog>
  </>
}
