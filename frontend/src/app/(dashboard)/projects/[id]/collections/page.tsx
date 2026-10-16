'use client'
import {useCallback,useEffect,useState} from 'react'
import {useParams} from 'next/navigation'
import {fetchApi,Run,SourceInfo,active,dateLabel,errorMessage,label} from '@/lib/research'
import { PlatformBadge } from '@/components/platform-badge'
import { CollectionHistory } from '@/components/collection-history'
import {distribution} from '@/lib/post-distribution.mjs'
import {Project} from '@/lib/api'
import {Panel,ErrorBox,field,button,secondary} from '@/components/research-ui'
export default function Collections(){
 const {id}=useParams<{id:string}>();const [runs,setRuns]=useState<Run[]>([]);const [sources,setSources]=useState<SourceInfo>();const [query,setQuery]=useState('');const [selected,setSelected]=useState(['instagram','tiktok','facebook']);const [from,setFrom]=useState('');const [to,setTo]=useState('');const [target,setTarget]=useState(500);const [pull,setPull]=useState<string>();const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
 const [percentages,setPercentages]=useState<Record<string,number>>({});
 const allocation=distribution(selected,target,percentages);
 const reload=useCallback(async()=>{setRuns(await fetchApi<Run[]>(`/projects/${id}/jobs`))},[id]);
 useEffect(()=>{Promise.all([fetchApi<Project>(`/projects/${id}`),fetchApi<SourceInfo>('/sources'),fetchApi<Run[]>(`/projects/${id}/jobs`)]).then(([p,s,r])=>{setSources(s);setRuns(r);setQuery(p.boolean_query||'');setFrom(p.date_from?.slice(0,10)||'');setTo(p.date_to?.slice(0,10)||'')}).catch(e=>setError(errorMessage(e)))},[id]);
 useEffect(()=>{if(!runs.some(r=>active(r.status)))return;const timer=setInterval(()=>reload().catch(e=>setError(errorMessage(e))),2500);return()=>clearInterval(timer)},[runs,reload]);
 const inFlight=runs.some(r=>r.pull_id===pull&&active(r.status));const fullExists=runs.some(r=>r.pull_id===pull&&r.mode==='collection');
 async function start(mode:'preview'|'collection'){
  setBusy(true);setError('');setNotice('');try{
   if(!query.trim()||!selected.length)throw new Error('Enter a search query and select at least one source.');
   if(allocation.error)throw new Error(allocation.error);
   if(!Number.isInteger(target)||target<100||target>5000)throw new Error('Choose a total between 100 and 5,000 posts.');
   if(from&&to&&from>to)throw new Error('Start date must be on or before end date.');
   const run=await fetchApi<Run>(`/projects/${id}/jobs`,{method:'POST',body:JSON.stringify({name:`${mode==='preview'?'Preview':'Collection'}: ${query.slice(0,80)}`,query,platforms:selected,date_from:from?from+'T00:00:00Z':null,date_to:to?to+'T23:59:59.999999Z':null,requested_post_count:target,platform_percentages:percentages,pull_id:pull||null,mode})});
   setPull(run.pull_id);setNotice(active(run.status)?'Run queued. Progress will update below.':run.status==='failed'?'Run could not start. See the recorded error below.':`Reused preview collected ${dateLabel(run.created_at)}; no additional requests.`);await reload()
  }catch(e){setError(errorMessage(e))}finally{setBusy(false)}
 }
 function resume(r:Run){setPercentages(r.platform_percentages||{});setPull(r.pull_id);setQuery(r.query_versions[0]?.boolean_query||'');setSelected(r.platforms);setFrom(r.date_from?.slice(0,10)||'');setTo(r.date_to?.slice(0,10)||'');setTarget(r.requested_post_count);setNotice('Continuing the existing pull.')}
 async function cancel(run:Run){try{await fetchApi(`/projects/${id}/jobs/${run.id}/cancel`,{method:'POST'});await reload()}catch(e){setError(errorMessage(e))}}
 return <div className="mx-auto max-w-6xl space-y-6 p-6"><div className="flex flex-wrap justify-between gap-3"><div><h1 className="text-2xl font-bold">Collections</h1><p className="mt-2 text-sm text-text-muted">Search across platforms and collect the conversations that matter.</p></div><button className={secondary} disabled={busy||inFlight} onClick={()=>{setPull(undefined);setPercentages({});setNotice('Ready for a new query pull.')}}>Start a new pull</button></div><ErrorBox message={error}/>{notice&&<p role="status" className="rounded-lg bg-primary/10 p-3 text-sm text-primary">{notice}</p>}
 <Panel><div className="space-y-5"><div className="flex flex-wrap justify-between gap-2"><h2 className="font-semibold">{pull?'Continue query pull':'New query pull'}</h2>{pull&&<span className="break-all text-xs text-text-muted">Current pull / {pull.slice(0,8)}</span>}</div><label className="block text-sm font-medium">Search terms<textarea className={field+' mt-2'} rows={3} maxLength={200} placeholder='"bike lane" OR "cycling infrastructure"' value={query} onChange={e=>setQuery(e.target.value)} disabled={inFlight||fullExists}/></label><p className="text-xs text-text-muted">Use AND, OR, and quotes to refine your search.</p>
 <div className="rounded-lg border border-border bg-background p-4">
  <div className="flex flex-wrap items-center justify-between gap-3"><label htmlFor="post-target" className="text-sm font-medium">Total post target</label><label className="flex items-center gap-2 text-sm"><input aria-label="Total post target" className={field+' w-28'} type="number" min={100} max={5000} value={target} onChange={e=>setTarget(Number(e.target.value))} disabled={inFlight||fullExists||busy}/><span>posts</span></label></div>
  <input id="post-target" className="mt-4 w-full accent-primary" type="range" min={100} max={5000} step={1} value={Math.min(5000,Math.max(100,target))} onChange={e=>setTarget(Number(e.target.value))} disabled={inFlight||fullExists||busy} aria-valuetext={`${target.toLocaleString()} posts`}/>
  <div className="mt-1 flex justify-between text-xs text-text-muted"><span>100 posts</span><span>5,000 posts</span></div>
 </div>
 <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-text-muted">Set a platform percentage, or leave it blank to split the remaining posts automatically.</p><button type="button" className="text-xs font-medium text-primary" disabled={inFlight||fullExists||busy} onClick={()=>setPercentages({})}>Reset to defaults</button></div>
 <div className="grid gap-3 sm:grid-cols-3">{sources?.sources.map(s=>{
  const checked=selected.includes(s.platform);const share=allocation.percentages[s.platform];
  return <div key={s.platform} className={`rounded-lg border p-3 text-sm ${checked?'border-primary/40 bg-primary/5':'border-border'}`}>
   <label className="flex items-center gap-3"><input type="checkbox" checked={checked} disabled={!!pull||busy} onChange={e=>{setSelected(v=>e.target.checked?[...v,s.platform]:v.filter(p=>p!==s.platform));setPercentages(v=>{const next={...v};delete next[s.platform];return next})}}/><span><PlatformBadge platform={s.platform}/><span className="mt-1 block text-xs text-text-muted">{s.configured?'Ready to collect':'Unavailable - missing provider key'}</span></span></label>
   {checked&&<div className="mt-4 border-t border-border pt-3"><label className="flex items-center justify-between gap-2 text-xs">Share of posts<span className="flex items-center gap-1"><input aria-label={`${label(s.platform)} percentage`} type="number" min={0} max={100} step="0.01" className={field+' w-24 text-right'} placeholder={share===undefined?'Auto':share.toFixed(2)} value={percentages[s.platform]??''} disabled={inFlight||fullExists||busy} onChange={e=>setPercentages(v=>{const next={...v};if(e.target.value==='')delete next[s.platform];else next[s.platform]=Number(e.target.value);return next})}/>%</span></label><p className="mt-2 text-xs text-text-muted">{s.platform in percentages?'Custom':'Automatic'}: {allocation.counts[s.platform]?.toLocaleString()??'-'} posts{share!==undefined?` (${Number(share.toFixed(2))}%)`:''}</p></div>}
  </div>
 })}</div>
 {allocation.error?<p role="alert" className="text-sm text-red-700">{allocation.error}</p>:<p role="status" className="text-xs text-text-muted">{target.toLocaleString()} posts allocated across {selected.length} selected platforms. Actual results may be lower.</p>}
 <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm">Start date (optional)<input className={field+' mt-2'} type="date" value={from} onChange={e=>setFrom(e.target.value)} disabled={inFlight||fullExists}/></label><label className="text-sm">End date (optional)<input className={field+' mt-2'} type="date" value={to} min={from} onChange={e=>setTo(e.target.value)} disabled={inFlight||fullExists}/></label></div>
 <details className="text-xs text-text-muted"><summary className="cursor-pointer font-medium">Search coverage & provider limits</summary><p className="mt-2 leading-relaxed">Previews aim for up to 20 posts per source. Unchanged previews and SociaVault pages are reused for 15 minutes. Dates do not guarantee complete coverage; the target may not be reached. Instagram has a maximum of 300 results per search and may require a new search for full collection.</p></details>
 <div className="flex flex-wrap gap-3"><button className={secondary} disabled={busy||inFlight||fullExists||!!allocation.error||!selected.length||!Number.isInteger(target)||target<100||target>5000} onClick={()=>start('preview')}>{busy?'Submitting...':'Search preview'}</button><button className={button} disabled={busy||inFlight||fullExists||!!allocation.error||!selected.length||!Number.isInteger(target)||target<100||target>5000} onClick={()=>start('collection')}>Collect up to {target.toLocaleString()} posts</button></div><p className="text-xs text-text-muted">{sources?.account_limit_warning || 'Collections use provider credits. Start with a preview and a focused query, and check your provider balance before larger pulls.'}</p></div></Panel>
 <CollectionHistory runs={runs} projectId={id} busy={busy} inFlight={inFlight} resume={resume} cancel={cancel}/>

 </div>
}
