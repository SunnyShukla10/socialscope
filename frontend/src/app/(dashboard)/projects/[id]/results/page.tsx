'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowUpRight, Check, ChevronDown, MessageCircle, RefreshCw, Search, SlidersHorizontal, ThumbsUp, X } from 'lucide-react'
import { PlatformBadge } from '@/components/platform-badge'
import { getPlatformInfo, PlatformIcon } from '@/components/platform-badge'
import { fetchApi, type Run, platforms, dateLabel, errorMessage } from '@/lib/research'
import { queryPulls, pullAnchor } from '@/lib/query-pulls'
import { Panel, ErrorBox, field, secondary } from '@/components/research-ui'

interface Post {
  id: string; platform: string; body: string; author_username?: string; published_at?: string
  url?: string; likes: number; comments: number; shares: number; views: number
}
interface PostPage { items: Post[]; total: number; total_pages: number }

export default function Results() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const params = useSearchParams()
  const runId = params.get('run_id') || ''
  const [data, setData] = useState<PostPage>({ items: [], total: 0, total_pages: 0 })
  const [runs, setRuns] = useState<Run[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [runsError, setRunsError] = useState('')
  const [search, setSearch] = useState('')
  const [sources, setSources] = useState<string[]>([])
  const [sort, setSort] = useState('date')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [advanced, setAdvanced] = useState(false)
  const requestVersion = useRef(0)
  const pulls = useMemo(() => queryPulls(runs), [runs])
  const selectedPull = pulls.find(pull => pull.entries.some(run => run.id === runId))
  const selectedRun = runs.find(run => run.id === runId)
  const hasFilters = Boolean(runId || search || sources.length || from || to || sort !== 'date')
  const invalidDates = Boolean(from && to && from > to)

  useEffect(() => {
    let current = true
    setRunsLoading(true)
    fetchApi<Run[]>(`/projects/${id}/jobs`).then(value => { if (current) { setRuns(value); setRunsError('') } })
      .catch(e => { if (current) setRunsError(errorMessage(e)) })
      .finally(() => { if (current) setRunsLoading(false) })
    return () => { current = false }
  }, [id, refresh])

  // Invalidate old responses immediately so rapid filter changes cannot show stale posts.
  useEffect(() => {
    const version = ++requestVersion.current
    if (invalidDates) { setLoading(false); return }
    setLoading(true)
    const timer = setTimeout(async () => {
      const query = new URLSearchParams({ scope: 'all', search, sort_by: sort, page: String(page), per_page: '25' })
      sources.forEach(source => query.append('platform', source))
      if (from) query.set('date_from', from + 'T00:00:00Z')
      if (to) query.set('date_to', to + 'T23:59:59.999999Z')
      if (runId) query.set('run_id', runId)
      try {
        const result = await fetchApi<PostPage>(`/projects/${id}/posts?${query}`)
        if (requestVersion.current === version) { setData(result); setError('') }
      } catch (e) {
        if (requestVersion.current === version) setError(errorMessage(e))
      } finally {
        if (requestVersion.current === version) setLoading(false)
      }
    }, 250)
    return () => { clearTimeout(timer); requestVersion.current++ }
  }, [id, search, sources, sort, from, to, page, runId, refresh, invalidDates])

  useEffect(() => { setPage(1) }, [runId])
  function chooseRun(value: string) {
    setPage(1)
    const query = new URLSearchParams(params.toString())
    if (value) query.set('run_id', value)
    else query.delete('run_id')
    router.replace(`/projects/${id}/results${query.size ? '?' + query : ''}`, { scroll: false })
  }
  function toggleSource(source: string) {
    setPage(1)
    setSources(current => current.includes(source) ? current.filter(p => p !== source) : [...current, source])
  }
  function clearFilters() {
    setSearch(''); setSources([]); setFrom(''); setTo(''); setSort('date'); setPage(1); chooseRun('')
  }

  return <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-3xl font-bold">Results</h1><p className="mt-2 text-sm text-text-muted">Explore conversations across your query pulls.</p></div>
      <button className={secondary + ' gap-2'} disabled={loading} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={15} className={loading ? 'animate-spin' : ''}/>{loading ? 'Updating' : 'Refresh'}</button>
    </div>
    <ErrorBox message={runsError}/>
    <Panel className="!p-0 overflow-hidden">
      <div className="space-y-4 p-4 sm:p-5">
        <div className="grid items-start gap-4 sm:grid-cols-2">
          <label className="block text-xs font-medium text-text-muted">Query pull
            <select className={field + ' mt-2 font-medium text-text'} aria-label="Query pull" value={selectedPull?.id || (runId ? '__selected' : '')} disabled={runsLoading} onChange={e => chooseRun(pulls.find(pull => pull.id === e.target.value)?.resultRun.id || '')}>
              <option value="">All query pulls</option>
              {runId && !selectedPull && <option value="__selected">{runsLoading ? 'Loading selected pull...' : 'Selected results'}</option>}
              {pulls.map(pull => <option key={pull.id} value={pull.id}>Pull {String(pull.number).padStart(2, '0')} - {pull.query}</option>)}
            </select>
          </label>
          <label className="block text-xs font-medium text-text-muted">Search posts
            <div className="relative mt-2"><Search size={16} aria-hidden="true" className="absolute left-3 top-2.5 text-text-muted"/><input className={field + ' pl-9'} placeholder="Search words or phrases" value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}/></div>
          </label>
        </div>
        {selectedPull && <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-background p-3">
          <div className="min-w-0 flex-1"><p className="break-words text-sm font-medium">{selectedRun?.query_versions[0]?.boolean_query || selectedPull.query}</p><p className="mt-1 text-xs text-text-muted">Showing this {selectedRun?.mode === 'preview' ? 'preview' : 'collection'} only.</p></div>
          <div className="flex flex-wrap items-center gap-3"><label className="text-xs text-text-muted">Results from<select aria-label="Results from" className={field + ' mt-1'} value={runId} onChange={e => chooseRun(e.target.value)}>{[...selectedPull.entries].reverse().map(run => <option key={run.id} value={run.id}>{run.mode === 'preview' ? 'Preview' : 'Collection'} - {dateLabel(run.created_at)} - {run.total_posts_collected.toLocaleString()} posts</option>)}</select></label><Link className="text-xs font-medium text-primary" href={`/projects/${id}/collections#${pullAnchor(selectedPull.id)}`}>Open pull</Link></div>
        </div>}
        <fieldset><legend className="mb-2 text-xs font-medium text-text-muted">Sources <span className="font-normal">/ Select one or more</span></legend>
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-pressed={sources.length === 0} onClick={() => { setSources([]); setPage(1) }} className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${sources.length === 0 ? 'border-primary bg-primary/10 text-primary' : 'border-border text-text-muted hover:bg-background'}`}>All sources</button>
            {platforms.map(source => {
              const info = getPlatformInfo(source)
              const selected = sources.includes(source)
              return <button key={source} type="button" aria-pressed={selected} onClick={() => toggleSource(source)} className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition-colors ${selected ? 'ring-1 ring-inset' : 'hover:bg-background'}`} style={{ color: selected ? info.color : undefined, borderColor: selected ? info.color : undefined, backgroundColor: selected ? `${info.color}12` : undefined, ...(selected ? { '--tw-ring-color': info.color } : {}) }}><span style={{ color: info.color }} aria-hidden="true"><PlatformIcon platform={source} size={14}/></span>{info.name}{selected && <Check size={12} aria-hidden="true"/>}</button>
            })}
          </div>
        </fieldset>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-background/50 px-4 py-3 sm:px-5">
        <button type="button" aria-expanded={advanced} aria-controls="date-filters" className="inline-flex items-center gap-2 text-xs font-medium text-text-muted" onClick={() => setAdvanced(value => !value)}><SlidersHorizontal size={14}/>{from || to ? 'Date filters applied' : 'Date filters'}<ChevronDown size={14} className={advanced ? 'rotate-180' : ''}/></button>
        <div className="flex flex-wrap items-center gap-4">{hasFilters && <button className="inline-flex items-center gap-1 text-xs font-medium text-primary" onClick={clearFilters}><X size={13}/>Reset filters</button>}<label className="flex items-center gap-2 text-xs text-text-muted">Sort<select aria-label="Sort results" className="rounded-lg border border-border bg-surface px-2 py-1.5 text-xs text-text" value={sort} onChange={e => { setSort(e.target.value); setPage(1) }}><option value="date">Newest first</option><option value="oldest">Oldest first</option><option value="most_engaged">Most engaged</option></select></label></div>
      </div>
      {advanced && <div id="date-filters" className="grid gap-3 border-t border-border p-4 sm:grid-cols-2 sm:px-5"><label className="text-xs text-text-muted">Published from<input type="date" className={field + ' mt-2'} value={from} max={to || undefined} onChange={e => { setFrom(e.target.value); setPage(1) }}/></label><label className="text-xs text-text-muted">Published through<input type="date" className={field + ' mt-2'} value={to} min={from} onChange={e => { setTo(e.target.value); setPage(1) }}/></label></div>}
    </Panel>
    <ErrorBox message={invalidDates ? 'The start date must be on or before the end date.' : error}/>
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-text-muted"><p role="status">{loading ? 'Finding posts...' : invalidDates || error ? 'Results unavailable' : `${data.total.toLocaleString()} ${data.total === 1 ? 'post' : 'posts'}${hasFilters ? ' matching your filters' : ' across this project'}`}</p>{!loading && !error && !invalidDates && data.total > 0 && <span>{(page - 1) * 25 + 1}-{Math.min(page * 25, data.total)} of {data.total.toLocaleString()}</span>}</div>
    {loading ? <div className="space-y-3" aria-label="Loading results">{[1, 2, 3].map(n => <Panel key={n} className="animate-pulse"><div className="h-5 w-40 rounded bg-border/50"/><div className="mt-5 h-4 w-full rounded bg-border/50"/><div className="mt-2 h-4 w-2/3 rounded bg-border/50"/></Panel>)}</div> : !error && !invalidDates && (data.items.length ? <div className="space-y-3">{data.items.map(post => <Panel key={post.id}>
      <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><PlatformBadge platform={post.platform}/><span className="text-sm font-semibold">{post.author_username || 'Author unavailable'}</span></div><time className="text-xs text-text-muted" dateTime={post.published_at}>{dateLabel(post.published_at)}</time></div>
      <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-relaxed">{post.body || 'No text provided by source'}</p>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-4 text-xs text-text-muted"><span className="inline-flex items-center gap-1.5"><ThumbsUp size={13}/>{post.likes.toLocaleString()} likes</span><span className="inline-flex items-center gap-1.5"><MessageCircle size={13}/>{post.comments.toLocaleString()} comments</span>{post.shares > 0 && <span>{post.shares.toLocaleString()} shares</span>}{post.views > 0 && <span>{post.views.toLocaleString()} views</span>}</div>{post.url && <a className="inline-flex items-center gap-1 text-xs font-medium text-primary" href={post.url} target="_blank" rel="noopener noreferrer">Original post<ArrowUpRight size={14}/></a>}</div>
    </Panel>)}</div> : <Panel className="py-10 text-center"><Search size={24} className="mx-auto text-text-muted"/><h2 className="mt-3 font-semibold">{hasFilters ? 'No posts match these filters' : 'No posts yet'}</h2><p className="mt-2 text-sm text-text-muted">{hasFilters ? 'Try another source, query pull, or date range.' : 'Start a query pull to collect conversations.'}</p>{hasFilters ? <button className="mt-4 text-sm font-medium text-primary" onClick={clearFilters}>Reset filters</button> : <Link className="mt-4 inline-block text-sm font-medium text-primary" href={`/projects/${id}/collections`}>New query pull</Link>}</Panel>)}
    {!error && !invalidDates && data.total_pages > 1 && <div className="flex items-center justify-between"><button className={secondary} disabled={loading || page <= 1} onClick={() => setPage(value => value - 1)}>Previous</button><span className="text-xs text-text-muted">Page {page} of {data.total_pages}</span><button className={secondary} disabled={loading || page >= data.total_pages} onClick={() => setPage(value => value + 1)}>Next</button></div>}
  </div>
}
