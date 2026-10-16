'use client'

import { useEffect, useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush } from 'recharts'
import { getAnalyticsVolume, getAnalyticsEngagement, type VolumeDataPoint, type EngagementResponse, type AnalyticsTimeFilters } from '@/lib/api'
import { fetchApi, type Run } from '@/lib/research'
import { queryPulls } from '@/lib/query-pulls'
import { PLATFORMS, PLATFORM_KEYS, CHART_COLORS } from '@/lib/constants'
import { formatNumber } from '@/lib/utils'
import { ErrorBox, field } from '@/components/research-ui'

const metrics = {
  likes: { name: 'Likes', color: '#20808D' },
  comments: { name: 'Comments', color: '#A84B2F' },
  shares: { name: 'Shares', color: '#7356A6' },
  views: { name: 'Views', color: '#1DA1F2' },
}
const dateLabel = (value: string) => new Date(`${value}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
const panel = 'rounded-xl border border-border bg-surface p-6'
const empty = 'flex h-64 items-center justify-center rounded-lg bg-background px-4 text-center text-sm text-text-muted'
const tooltipStyle = { background: '#F9F8F5', border: '1px solid #D4D1CA', borderRadius: 8, fontSize: 12 }

export function AnalyticsTimeCharts({ projectId }: { projectId: string }) {
  const [platform, setPlatform] = useState('')
  const [pullId, setPullId] = useState('')
  const [runs, setRuns] = useState<Run[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [runsError, setRunsError] = useState('')
  const [volume, setVolume] = useState<VolumeDataPoint[]>([])
  const [engagement, setEngagement] = useState<EngagementResponse>({ data: [], metrics: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [zoom, setZoom] = useState<{ startIndex: number; endIndex: number } | null>(null)
  const pulls = queryPulls(runs)
  // Both brushes use the same ordered dates, even if one endpoint has gaps.
  // Keep chart data stable while dragging so Recharts does not reset the brush.
  const timeline = useMemo(() => Array.from(new Set([
    ...volume.map(point => point.date), ...engagement.data.map(point => point.date),
  ])).sort(), [volume, engagement.data])
  const volumeChartData = useMemo(() => {
    const byDate = new Map(volume.map(point => [point.date, point]))
    const keys = Array.from(new Set(volume.flatMap(point => Object.keys(point).filter(key => key !== 'date'))))
    return timeline.map(date => byDate.get(date) || { date, ...Object.fromEntries(keys.map(key => [key, 0])) })
  }, [volume, timeline])
  const engagementChartData = useMemo(() => {
    const byDate = new Map(engagement.data.map(point => [point.date, point]))
    return timeline.map(date => byDate.get(date) || { date, likes: 0, comments: 0, shares: 0, views: 0 })
  }, [engagement.data, timeline])
  const lastIndex = Math.max(0, timeline.length - 1)
  const startIndex = Math.min(zoom?.startIndex ?? 0, lastIndex)
  const endIndex = Math.max(startIndex, Math.min(zoom?.endIndex ?? lastIndex, lastIndex))
  const isZoomed = startIndex > 0 || endIndex < lastIndex
  const postTotals = useMemo(() => {
    const totals = [0]
    for (const point of volumeChartData) {
      const count = Object.entries(point).reduce((sum, [key, value]) => key === 'date' ? sum : sum + Number(value), 0)
      totals.push(totals[totals.length - 1] + count)
    }
    return totals
  }, [volumeChartData])
  const totalPosts = postTotals[postTotals.length - 1]
  const visiblePosts = volumeChartData.length ? postTotals[endIndex + 1] - postTotals[startIndex] : 0
  function changeZoom(range: { startIndex?: number; endIndex?: number }) {
    const start = Math.max(0, Math.min(range.startIndex ?? startIndex, lastIndex))
    const end = Math.max(start, Math.min(range.endIndex ?? endIndex, lastIndex))
    setZoom(previous => previous?.startIndex === start && previous?.endIndex === end
      ? previous : { startIndex: start, endIndex: end })
  }
  const zoomControls = !loading && !error && timeline.length > 0 && <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-xs">
    <p className="text-text-muted" aria-live="polite">Showing {dateLabel(timeline[startIndex])} to {dateLabel(timeline[endIndex])}</p>
    <button type="button" className="font-medium text-primary disabled:opacity-40" disabled={!isZoomed} onClick={() => setZoom(null)}>Reset zoom</button>
  </div>

  useEffect(() => {
    let cancelled = false
    setRunsLoading(true)
    setRunsError('')
    fetchApi<Run[]>(`/projects/${projectId}/jobs`).then(value => {
      if (!cancelled) setRuns(value)
    }).catch(() => {
      if (!cancelled) setRunsError('Query pulls could not load. Retry to filter by pull.')
    }).finally(() => { if (!cancelled) setRunsLoading(false) })
    return () => { cancelled = true }
  }, [projectId, revision])

  useEffect(() => {
    let cancelled = false
    const filters: AnalyticsTimeFilters = { platform: platform || undefined }
    if (pullId) {
      const run = runs.find(value => (value.pull_id || value.id) === pullId)
      if (run?.pull_id) filters.pull_id = run.pull_id
      else filters.run_id = pullId
    }
    setLoading(true)
    setZoom(null)
    setError('')
    setVolume([])
    setEngagement({ data: [], metrics: [] })
    Promise.all([getAnalyticsVolume(projectId, filters), getAnalyticsEngagement(projectId, filters)])
      .then(([volumeData, engagementData]) => {
        if (cancelled) return
        setVolume(volumeData)
        setEngagement(engagementData)
      }).catch(() => {
        if (!cancelled) setError('These charts could not load. Retry to fetch the selected platform and pull.')
      }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [projectId, platform, pullId, runs, revision])

  const activePlatforms = Array.from(new Set(volume.flatMap(point => Object.keys(point).filter(key => key !== 'date'))))
  return <section className="space-y-6" aria-label="Volume and engagement trends">
    <div className={panel}>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">Volume Over Time</h3>
          {!loading && !error && <span aria-label="Posts in volume graph" aria-live="polite" className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            {isZoomed ? `${visiblePosts.toLocaleString()} of ${totalPosts.toLocaleString()} posts in view` : `${totalPosts.toLocaleString()} ${totalPosts === 1 ? 'post' : 'posts'}`}
          </span>}
        </div><p className="mt-2 text-xs text-text-muted">Filters apply to both charts below.</p></div>
        <div className="flex w-full flex-wrap gap-3 sm:w-auto">
          <label className="min-w-0 flex-1 text-xs font-medium sm:w-40">Platform<select aria-label="Platform" className={field + ' mt-2'} value={platform} onChange={event => setPlatform(event.target.value)}>
            <option value="">All platforms</option>{PLATFORM_KEYS.map(key => <option key={key} value={key}>{PLATFORMS[key].name}</option>)}
          </select></label>
          <label className="min-w-0 flex-1 text-xs font-medium sm:w-64">Query pull<select aria-label="Query pull" className={field + ' mt-2'} value={pullId} disabled={runsLoading} onChange={event => setPullId(event.target.value)}>
            <option value="">All pulls</option>{pulls.map(pull => <option key={pull.id} value={pull.id}>Pull {pull.number}: {pull.query.slice(0, 80)}</option>)}
          </select></label>
          {(platform || pullId) && <button type="button" className="text-xs font-medium text-primary" onClick={() => { setPlatform(''); setPullId('') }}>Reset filters</button>}
        </div>
      </div>
      <p className="mb-4 text-xs text-text-muted">Unique included posts by publication date. A pull includes its previews and full collection; repeated posts count once.</p>
      <p className="mb-3 text-xs text-text-muted">Drag the handles below either chart to zoom, or drag the selected range to move through time. Both charts stay in sync.</p>
      {zoomControls}
      <ErrorBox message={runsError || error}/>
      {(runsError || error) && <button className="my-3 text-sm font-medium text-primary" onClick={() => setRevision(value => value + 1)}>Retry charts</button>}
      {loading ? <div role="status" className="h-64 animate-pulse rounded bg-border/20"><span className="sr-only">Loading charts</span></div> : error ? null : !volume.length ? <div className={empty}>No dated posts match this platform and pull.</div> :
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={volumeChartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#D4D1CA" strokeOpacity={0.6}/>
            <XAxis dataKey="date" tickFormatter={dateLabel} tick={{fontSize: 10, fill: '#7A7974'}} tickLine={false} minTickGap={45} interval="preserveStartEnd"/>
            <YAxis allowDecimals={false} tickFormatter={formatNumber} tick={{fontSize: 11, fill: '#7A7974'}} width={48} axisLine={false} tickLine={false}/>
            <Tooltip labelFormatter={dateLabel} formatter={(value: number) => value.toLocaleString()} contentStyle={tooltipStyle}/>
            <Legend wrapperStyle={{fontSize: 12}}/>
            {activePlatforms.map((key, index) => <Line key={key} isAnimationActive={false} type="linear" dataKey={key} name={PLATFORMS[key as keyof typeof PLATFORMS]?.name || key} stroke={PLATFORMS[key as keyof typeof PLATFORMS]?.color || CHART_COLORS[index % CHART_COLORS.length]} strokeWidth={2} dot={startIndex === endIndex} activeDot={{r: 4}}/>) }
            {timeline.length > 1 && <Brush dataKey="date" height={32} travellerWidth={14} stroke="#20808D" fill="#F9F8F5" tickFormatter={dateLabel} startIndex={startIndex} endIndex={endIndex} onChange={changeZoom} ariaLabel="Volume date range">
              <LineChart>{activePlatforms.map((key, index) => <Line key={key} dataKey={key} stroke={PLATFORMS[key as keyof typeof PLATFORMS]?.color || CHART_COLORS[index % CHART_COLORS.length]} dot={false} isAnimationActive={false}/>)}</LineChart>
            </Brush>}
          </LineChart>
        </ResponsiveContainer>}
    </div>
    <div className={panel}>
      <h3 className="text-sm font-semibold">Engagement Over Time</h3>
      <p className="mb-5 mt-2 text-xs text-text-muted">Uses the platform and pull selected above. Recorded totals on posts published each day, as observed during collection; this is not the date each interaction occurred. Views use the right axis.</p>
      {zoomControls}
      {loading ? <div className="h-64 animate-pulse rounded bg-border/20"/> : error ? <div className={empty}>Engagement could not load. Use Retry charts above.</div> : !engagement.metrics.length ? <div className={empty}>No recorded engagement metrics for this platform and pull. Providers may omit metrics or report zero.</div> :
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={engagementChartData} margin={{top: 5, right: 5, left: 0, bottom: 5}}>
            <CartesianGrid strokeDasharray="3 3" stroke="#D4D1CA" strokeOpacity={0.6}/>
            <XAxis dataKey="date" tickFormatter={dateLabel} tick={{fontSize: 10, fill: '#7A7974'}} tickLine={false} minTickGap={45} interval="preserveStartEnd"/>
            <YAxis yAxisId="interactions" hide={!engagement.metrics.some(metric => metric !== 'views')} allowDecimals={false} tickFormatter={formatNumber} tick={{fontSize: 11, fill: '#7A7974'}} width={48} axisLine={false} tickLine={false}/>
            <YAxis yAxisId="views" orientation="right" hide={!engagement.metrics.includes('views')} allowDecimals={false} tickFormatter={formatNumber} tick={{fontSize: 11, fill: '#1DA1F2'}} width={48} axisLine={false} tickLine={false}/>
            <Tooltip labelFormatter={dateLabel} formatter={(value: number) => value.toLocaleString()} contentStyle={tooltipStyle}/>
            <Legend wrapperStyle={{fontSize: 12}}/>
            {engagement.metrics.map(metric => <Line key={metric} isAnimationActive={false} type="linear" dataKey={metric} name={metrics[metric].name} stroke={metrics[metric].color} yAxisId={metric === 'views' ? 'views' : 'interactions'} strokeWidth={2} dot={startIndex === endIndex} activeDot={{r: 4}}/>)}
            {timeline.length > 1 && <Brush dataKey="date" height={32} travellerWidth={14} stroke="#20808D" fill="#F9F8F5" tickFormatter={dateLabel} startIndex={startIndex} endIndex={endIndex} onChange={changeZoom} ariaLabel="Engagement date range">
              <LineChart><Line dataKey={engagement.metrics[0]} stroke={metrics[engagement.metrics[0]].color} dot={false} isAnimationActive={false}/></LineChart>
            </Brush>}
          </LineChart>
        </ResponsiveContainer>}
      {!!engagement.metrics.length && <p className="mt-3 text-xs text-text-muted">Only metrics with recorded values above zero are shown. Missing provider metrics may be stored as zero.</p>}
    </div>
  </section>
}
