'use client'

import { useState, type ReactNode } from 'react'
import Link from 'next/link'
import { Search } from 'lucide-react'
import { type Run, active, dateLabel } from '@/lib/research'
import { PlatformBadge } from '@/components/platform-badge'
import { Badge } from '@/components/ui/badge'
import { Panel, field, secondary } from '@/components/research-ui'

const accents = ['border-l-primary', 'border-l-violet-500', 'border-l-amber-500', 'border-l-sky-500', 'border-l-rose-500']
function statusVariant(status: string): 'success' | 'warning' | 'danger' | 'info' | 'muted' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'completed_with_errors' || status === 'cancelling') return 'warning'
  return active(status) ? 'info' : 'muted'
}

export function CollectionHistory({ runs, projectId, busy, inFlight, resume, cancel, renderBudget }: {
  runs: Run[]; projectId: string; busy: boolean; inFlight: boolean
  resume: (run: Run) => void; cancel: (run: Run) => void; renderBudget: (run: Run) => ReactNode
}) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const grouped = new Map<string, Run[]>()
  const ordered = [...runs].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id.localeCompare(b.id))
  ordered.forEach(run => {
    const key = run.pull_id || run.id
    grouped.set(key, [...(grouped.get(key) || []), run])
  })
  const pulls = Array.from(grouped.entries()).map(([id, entries], index) => ({ id, entries, number: index + 1 }))
    .reverse().filter(({ entries }) => entries.some(run =>
      [run.name, ...run.query_versions.map(q => q.boolean_query)].join(' ').toLowerCase().includes(search.trim().toLowerCase())
    ) && (!status || (status === 'active' ? active(entries[entries.length - 1].status) : entries[entries.length - 1].status === status)))

  return <section className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-lg font-semibold">Query pulls</h2><p className="mt-1 text-sm text-text-muted">{grouped.size} pulls · {runs.length} previews and collections</p></div>
    </div>
    {runs.length > 0 && <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-0 flex-1"><Search size={15} aria-hidden="true" className="absolute left-3 top-3 text-text-muted"/><input aria-label="Search query pulls" className={field + ' pl-9'} placeholder="Find a query or collection" value={search} onChange={e => setSearch(e.target.value)}/></div>
      <select aria-label="Filter pull status" className={field + ' sm:!w-auto'} value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option><option value="active">In progress</option><option value="completed">Completed</option><option value="completed_with_errors">Completed with errors</option><option value="failed">Failed</option><option value="cancelled">Cancelled</option></select>
      {(search || status) && <button className="text-sm text-primary" onClick={() => { setSearch(''); setStatus('') }}>Clear filters</button>}
    </div>}
    {!pulls.length && <Panel><p className="text-sm text-text-muted">{runs.length ? 'No query pulls match these filters.' : 'Your query pulls will appear here after your first search.'}</p></Panel>}
    {pulls.map(({ id, entries, number }) => {
      const latest = entries[entries.length - 1]
      const platforms = Array.from(new Set(entries.flatMap(r => r.platforms)))
      return <Panel key={id} className={`border-l-4 ${accents[(number - 1) % accents.length]}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Pull {number.toString().padStart(2, '0')} · {dateLabel(entries[0].created_at)}</p><h3 className="mt-2 break-words text-lg font-semibold">{entries[0].query_versions[0]?.boolean_query || entries[0].name}</h3></div>
          <Badge variant={statusVariant(latest.status)}>{latest.status.replaceAll('_', ' ')}</Badge>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">{platforms.map(p => <PlatformBadge key={p} platform={p}/>)}</div>
        <p className="mt-3 text-xs text-text-muted">{latest.date_from || latest.date_to ? `${latest.date_from ? dateLabel(latest.date_from) : 'Any start date'} to ${latest.date_to ? dateLabel(latest.date_to) : 'Any end date'}` : 'Provider default dates'} · Target: {latest.requested_post_count.toLocaleString()} posts</p>
        <div className="mt-5 divide-y divide-border border-t border-border">
          {entries.map(run => <div key={run.id} className="py-4 last:pb-0">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2"><span className={`rounded-md px-2 py-1 text-xs font-semibold ${run.mode === 'preview' ? 'bg-violet-50 text-violet-700' : 'bg-primary/10 text-primary'}`}>{run.mode === 'preview' ? 'Preview' : 'Collection'}</span><Badge variant={statusVariant(run.status)}>{run.status.replaceAll('_', ' ')}</Badge><span className="text-sm font-medium">{run.total_posts_collected.toLocaleString()} posts</span><span className="text-xs text-text-muted">{dateLabel(run.created_at)}</span></div>
              <div className="flex flex-wrap gap-2">{active(run.status) ? <button className={secondary} disabled={run.status === 'cancelling'} onClick={() => cancel(run)}>Cancel</button> : run.mode === 'preview' && !entries.some(r => r.mode === 'collection') && <button className={secondary} disabled={busy || inFlight} onClick={() => resume(run)}>Continue pull</button>}<Link className={secondary} href={`/projects/${projectId}/results?run_id=${run.id}`}>View results</Link></div>
            </div>
            {run.query_versions[0]?.boolean_query !== entries[0].query_versions[0]?.boolean_query && <p className="mt-3 rounded-lg bg-background p-3 text-sm">{run.query_versions[0]?.boolean_query}</p>}
            {run.error_message && <p role="status" className="mt-3 text-sm text-red-700">{run.error_message}</p>}
            <details className="mt-3"><summary className="cursor-pointer text-xs font-medium text-text-muted">Source breakdown & collection details</summary>
              <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-border text-xs text-text-muted"><th className="p-2">Platform</th><th className="p-2">Requested</th><th className="p-2">Collected</th><th className="p-2">Outcome</th></tr></thead><tbody>{run.platforms.map(p => <tr key={p} className="border-b border-border"><td className="p-2"><PlatformBadge platform={p}/></td><td className="p-2">{run.platform_allocations[p] || 0}</td><td className="p-2">{run.platform_states[p]?.posts_collected || 0}</td><td className="p-2 text-xs">{run.platform_states[p]?.provider_stop_reason || run.platform_states[p]?.status}<p className="mt-1 text-red-700">{run.platform_states[p]?.error}</p>{run.platform_states[p]?.provider_stop_details && <details className="mt-2"><summary className="cursor-pointer">Diagnostics</summary><pre className="whitespace-pre-wrap break-all">{JSON.stringify(run.platform_states[p].provider_stop_details, null, 2)}</pre></details>}</td></tr>)}</tbody></table></div>
              <div className="mt-3">{renderBudget(run)}</div><p className="mt-3 break-all text-xs text-text-muted">Pull ID: {id} · Run ID: {run.id}</p>
            </details>
            {run.preview_examples?.length > 0 && <details className="mt-3"><summary className="cursor-pointer text-xs font-medium text-primary">Preview examples ({run.preview_examples.length})</summary><div className="mt-3 grid gap-3 md:grid-cols-2">{run.preview_examples.slice(0,12).map(post => <article key={post.id} className="rounded-lg bg-background p-3"><div className="flex flex-wrap items-center gap-2"><PlatformBadge platform={post.platform}/><span className="text-xs text-text-muted">{dateLabel(post.published_at)}</span></div><p className="mt-2 whitespace-pre-wrap break-words text-sm">{post.body.slice(0,600)}</p>{post.url && <a href={post.url} target="_blank" rel="noopener noreferrer" className="mt-2 block text-xs text-primary">Original post</a>}</article>)}</div><p className="mt-3 text-xs text-text-muted">Preview examples are not a representative sample or a prediction of collection yield.</p></details>}
          </div>)}
        </div>
      </Panel>
    })}
  </section>
}
