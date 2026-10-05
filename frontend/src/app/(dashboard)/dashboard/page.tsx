'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { fetchApi, errorMessage, type SourceInfo } from '@/lib/research'
import { type Project } from '@/lib/api'
import { PlatformBadge } from '@/components/platform-badge'
import { Panel, ErrorBox, button } from '@/components/research-ui'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [sources, setSources] = useState<SourceInfo>()
  const [error, setError] = useState('')
  useEffect(() => { Promise.all([fetchApi<Project[]>('/projects'), fetchApi<SourceInfo>('/sources')]).then(([p, s]) => { setProjects(p); setSources(s) }).catch(e => setError(errorMessage(e))) }, [])
  const recent = [...projects].sort((a,b) => Date.parse(b.last_activity || b.created_at) - Date.parse(a.last_activity || a.created_at)).slice(0,5)
  return <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-bold">Your listening workspace</h1><p className="mt-3 text-text-muted">Explore conversations. Find patterns. Build your next insight.</p></div><Link className={button} href="/projects/new">New project</Link></div>
    <ErrorBox message={error}/>
    <div className="grid gap-4 sm:grid-cols-3">{[['Projects', projects.length], ['Collected posts', projects.reduce((sum,p) => sum+p.post_count,0)], ['Active projects', projects.filter(p=>p.status==='active').length]].map(([title,n]) => <Panel key={title}><p className="text-sm text-text-muted">{title}</p><p className="mt-2 text-3xl font-bold">{Number(n).toLocaleString()}</p></Panel>)}</div>
    <Panel><div className="flex justify-between"><h2 className="font-semibold">Recent projects</h2><Link className="text-sm text-primary" href="/projects">View all</Link></div>{recent.length ? recent.map(p => <Link key={p.id} className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-4 hover:bg-background" href={`/projects/${p.id}`}><div><span className="font-medium">{p.name}</span><div className="mt-2 flex flex-wrap gap-1.5">{p.platforms?.map(platform=><PlatformBadge key={platform} platform={platform}/>)}</div></div><span className="text-sm text-text-muted">{p.post_count.toLocaleString()} posts</span></Link>) : <p className="mt-4 text-sm text-text-muted">Create a project to start exploring a topic.</p>}</Panel>
    <Panel><h2 className="font-semibold">Your platforms</h2><div className="mt-4 grid gap-3 sm:grid-cols-3">{sources?.sources.map(s=><div key={s.platform} className="rounded-lg bg-background p-3"><PlatformBadge platform={s.platform}/><p className={`mt-2 text-xs ${s.configured ? 'text-emerald-700' : 'text-text-muted'}`}>{s.configured ? 'Connected' : 'Setup required'}</p></div>)}</div></Panel>
  </div>
}
