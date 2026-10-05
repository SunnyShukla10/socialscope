'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { fetchApi, dateLabel, errorMessage, type Run } from '@/lib/research'
import { type Project } from '@/lib/api'
import { PlatformBadge } from '@/components/platform-badge'
import { Panel, ErrorBox, button, secondary } from '@/components/research-ui'

export default function Overview() {
  const { id } = useParams<{id:string}>()
  const [project, setProject] = useState<Project>()
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState('')
  useEffect(() => { Promise.all([fetchApi<Project>(`/projects/${id}`),fetchApi<Run[]>(`/projects/${id}/jobs`)]).then(([p,r])=>{setProject(p);setRuns(r)}).catch(e=>setError(errorMessage(e))) },[id])
  const latest = [...runs].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at))[0]
  return <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6"><ErrorBox message={error}/>{project ? <>
    <div><h1 className="text-3xl font-bold">{project.name}</h1>{(project.research_question || project.description) && <p className="mt-3 max-w-3xl text-text-muted">{project.research_question || project.description}</p>}<div className="mt-4 flex flex-wrap gap-2">{project.platforms?.map(p=><PlatformBadge key={p} platform={p}/>)}</div></div>
    <div className="flex flex-wrap gap-3"><Link className={button} href={`/projects/${id}/results`}>View results</Link><Link className={secondary} href={`/projects/${id}/collections`}>New query pull</Link></div>
    <div className="grid gap-4 sm:grid-cols-3"><Panel><p className="text-sm text-text-muted">Collected posts</p><p className="mt-2 text-3xl font-bold">{project.post_count.toLocaleString()}</p><p className="mt-2 text-xs text-text-muted">Includes previews and excluded posts</p></Panel><Panel><p className="text-sm text-text-muted">Query pulls</p><p className="mt-2 text-3xl font-bold">{new Set(runs.map(r=>r.pull_id || r.id)).size}</p></Panel><Panel><p className="text-sm text-text-muted">Latest collection</p><p className="mt-2 font-semibold capitalize">{latest?.status.replaceAll('_',' ') || 'No collections yet'}</p>{latest && <p className="mt-2 text-xs text-text-muted">{dateLabel(latest.created_at)}</p>}</Panel></div>
    {(project.date_from || project.date_to) && <Panel><h2 className="font-semibold">Research period</h2><p className="mt-2 text-sm">{project.date_from || 'Any start date'} to {project.date_to || 'Any end date'}</p><p className="mt-2 text-xs text-text-muted">Each query pull keeps its own dates. Availability varies by platform.</p></Panel>}
    {latest && <Panel><div className="flex flex-wrap justify-between gap-3"><h2 className="font-semibold">Latest query</h2><Link className="text-sm text-primary" href={`/projects/${id}/collections`}>View all pulls</Link></div><p className="mt-3 break-words rounded-lg bg-background p-3 text-sm">{latest.query_versions[0]?.boolean_query || latest.name}</p></Panel>}
  </> : !error && <p>Loading project...</p>}</div>
}
