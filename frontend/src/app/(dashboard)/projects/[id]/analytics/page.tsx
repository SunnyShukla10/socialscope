'use client'

import React, { useEffect, useState } from 'react'
import {ErrorBox} from '@/components/research-ui'
import { useParams } from 'next/navigation'
import {
  getAnalyticsOverview,
  getAnalyticsVolume,
  getAnalyticsPlatforms,
  getAnalyticsHashtags,
  getAnalyticsWordMap,
  type AnalyticsOverview,
  type VolumeDataPoint,
  type PlatformDataPoint,
  type HashtagDataPoint,
  type WordMapResponse,
} from '@/lib/api'
import { KpiCard } from '@/components/kpi-card'
import { ProjectBackButton } from '@/components/project-back-button'
import { SkeletonKPI } from '@/components/ui/skeleton'
import { formatNumber, formatDateShort } from '@/lib/utils'
import { CHART_COLORS, PLATFORMS } from '@/lib/constants'
import { MessageSquare, Users, Hash, Heart, AlertCircle, Sparkles, RefreshCw } from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'


const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ color: string; name: string; value: number }>; label?: string }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface border border-border rounded-lg shadow-lg px-4 py-3 text-xs">
        <p className="font-semibold text-text mb-2">{label}</p>
        {payload.map((entry) => (
          <div key={entry.name} className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-text-muted">{entry.name}:</span>
            <span className="font-medium text-text">{entry.value?.toLocaleString()}</span>
          </div>
        ))}
      </div>
    )
  }
  return null
}

function CoOccurrenceNetwork({ wordMap }: { wordMap: WordMapResponse }) {
  const edges = wordMap.edges.slice(0, 10)
  const connectedIds = new Set(edges.flatMap((edge) => [edge.source, edge.target]))
  const nodeById = new Map(wordMap.nodes.map((node) => [node.id, node]))
  const nodes = Array.from(connectedIds).map((id) => nodeById.get(id) ?? {
    id,
    label: id,
    count: edges.reduce((total, edge) => {
      return total + (edge.source === id || edge.target === id ? edge.weight || edge.count : 0)
    }, 0),
  })
  const maxNode = Math.max(1, ...nodes.map((node) => node.value || node.count))
  const maxEdgeWeight = Math.max(1, ...edges.map((edge) => edge.weight || edge.count))
  const width = 760
  const height = 430
  const centerX = width / 2
  const centerY = height / 2
  const radius = 155
  const positions = new Map(
    nodes.map((node, index) => {
      const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2
      return [
        node.id,
        {
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius,
        },
      ]
    })
  )

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-background">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Keyword co-occurrence network" className="h-80 w-full">
        {edges.map((edge, index) => {
          const weight = edge.weight || edge.count
          const source = positions.get(edge.source)
          const target = positions.get(edge.target)
          if (!source || !target) return null
          return (
            <g key={`${edge.source}-${edge.target}-${index}`}>
              <line
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#20808D"
                strokeOpacity={0.18 + 0.35 * (weight / maxEdgeWeight)}
                strokeWidth={1 + 4 * (weight / maxEdgeWeight)}
              >
                <title>{`${edge.source} + ${edge.target}: ${weight.toLocaleString()} co-occurrences`}</title>
              </line>
            </g>
          )
        })}
        {nodes.map((node) => {
          const pos = positions.get(node.id)
          if (!pos) return null
          const value = node.value || node.count
          const r = 7 + (value / maxNode) * 10
          const dx = pos.x - centerX
          const dy = pos.y - centerY
          const length = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const labelX = pos.x + (dx / length) * (r + 22)
          const labelY = pos.y + (dy / length) * (r + 22)
          const anchor = Math.abs(dx) < 24 ? 'middle' : dx > 0 ? 'start' : 'end'
          const label = node.label || node.id
          return (
            <g key={node.id}>
              <circle cx={pos.x} cy={pos.y} r={r} fill="#20808D" opacity={0.9}>
                <title>{`${label}: ${value.toLocaleString()}`}</title>
              </circle>
              <text
                x={labelX}
                y={labelY}
                textAnchor={anchor}
                dominantBaseline="middle"
                fill="#252420"
                className="text-[11px]"
                paintOrder="stroke"
                stroke="#F9F8F5"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                {label.length > 14 ? `${label.slice(0, 13)}...` : label}
              </text>
            </g>
          )
        })}
        {nodes.length === 0 && (
          <text x={centerX} y={centerY} textAnchor="middle" fill="#7A7974" className="text-[12px]">
            No co-occurrence pairs available
          </text>
        )}
      </svg>
      {wordMap.edges.length > edges.length && (
        <p className="mt-2 text-xs text-text-muted">
          Showing the strongest {edges.length} pairs from the co-occurrence set.
        </p>
      )}
    </div>
  )
}

export default function AnalyticsPage() {
  const params = useParams()
  const id = params.id as string

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [volume, setVolume] = useState<VolumeDataPoint[]>([])
  const [platforms, setPlatforms] = useState<PlatformDataPoint[]>([])
  const [hashtags, setHashtags] = useState<HashtagDataPoint[]>([])
  const [wordMap, setWordMap] = useState<WordMapResponse>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      const [overviewRes, volumeRes, platRes, hashRes, wordMapRes] = await Promise.allSettled([
        getAnalyticsOverview(id),
        getAnalyticsVolume(id),
        getAnalyticsPlatforms(id),
        getAnalyticsHashtags(id),
        getAnalyticsWordMap(id),
      ])

      setError([overviewRes,volumeRes,platRes,hashRes,wordMapRes].some(r => r.status === 'rejected') ? 'Some analytics could not load. Check the API connection and refresh this page.' : '')
      setOverview(overviewRes.status === 'fulfilled' ? overviewRes.value : null)
      setVolume(volumeRes.status === 'fulfilled' ? volumeRes.value : [])
      setPlatforms(platRes.status === 'fulfilled' ? platRes.value : [])
      setHashtags(hashRes.status === 'fulfilled' ? hashRes.value : [])
      setWordMap(wordMapRes.status === 'fulfilled' ? wordMapRes.value : { nodes: [], edges: [] })
      setLoading(false)
    }
    load()
  }, [id])

  const activePlatforms = Array.from(new Set(volume.flatMap(point => Object.keys(point).filter(k => k !== "date"))))


  return (
    <div className="p-6 max-w-7xl space-y-6">
      <p className="text-sm text-text-muted">Scope: unique posts included in analysis. Search results are not representative of a population.</p>

      <ErrorBox message={error}/>
      {/* KPI row */}
      {loading ? (
        <SkeletonKPI count={4} />
      ) : overview ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Total Posts"
            value={formatNumber(overview.total_posts)}
            delta={overview.posts_delta}
            deltaLabel="vs last period"
            icon={<MessageSquare size={18} />}
          />
          <KpiCard
            label="Unique Authors"
            value={formatNumber(overview.unique_authors)}
            delta={overview.authors_delta}
            deltaLabel="vs last period"
            icon={<Users size={18} />}
          />
          <KpiCard
            label="Top Hashtags"
            value={formatNumber(overview.top_hashtags)}
            deltaLabel="tracked terms"
            icon={<Hash size={18} />}
          />
          <KpiCard
            label="Total Engagement"
            value={formatNumber(overview.total_engagement)}
            delta={overview.engagement_delta}
            deltaLabel="vs last period"
            icon={<Heart size={18} />}
          />
        </div>
      ) : null}

      {/* Volume over time */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h3 className="text-sm font-semibold text-text mb-5">Volume Over Time</h3>
        {loading ? (
          <div className="h-64 bg-border/20 rounded animate-pulse" />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={volume} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#D4D1CA" strokeOpacity={0.6} />
              <XAxis
                dataKey="date"
                tickFormatter={(v) => formatDateShort(v)}
                tick={{ fontSize: 11, fill: '#7A7974' }}
                axisLine={{ stroke: '#D4D1CA' }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#7A7974' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatNumber(v)}
                width={45}
              />
              <Tooltip content={<CustomTooltip />} />
              {activePlatforms.map((p, i) => (
                <Line
                  key={p}
                  type="monotone"
                  dataKey={p}
                  stroke={PLATFORMS[p as keyof typeof PLATFORMS]?.color || CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  name={p}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Platform distribution */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h3 className="text-sm font-semibold text-text mb-5">Platform Distribution</h3>
        {loading ? (
          <div className="h-64 bg-border/20 rounded animate-pulse" />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={platforms}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 50, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#D4D1CA" strokeOpacity={0.6} horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: '#7A7974' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatNumber(v)}
              />
              <YAxis
                type="category"
                dataKey="platform"
                tick={{ fontSize: 11, fill: '#7A7974' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: string) => PLATFORMS[v as keyof typeof PLATFORMS]?.name || v}
                width={70}
              />
              <Tooltip
                formatter={(value: number) => [value.toLocaleString(), 'Posts']}
                contentStyle={{
                  background: '#F9F8F5',
                  border: '1px solid #D4D1CA',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {platforms.map((entry, i) => (
                  <Cell
                    key={entry.platform}
                    fill={PLATFORMS[entry.platform as keyof typeof PLATFORMS]?.color || CHART_COLORS[i % CHART_COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top hashtags */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h3 className="text-sm font-semibold text-text mb-5">Top 15 Hashtags</h3>
        {loading ? (
          <div className="h-72 bg-border/20 rounded animate-pulse" />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={hashtags.slice(0, 15)}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#D4D1CA" strokeOpacity={0.6} horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: '#7A7974' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatNumber(v)}
              />
              <YAxis
                type="category"
                dataKey="hashtag"
                tick={{ fontSize: 11, fill: '#7A7974' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: string) => `#${v}`}
                width={95}
              />
              <Tooltip
                formatter={(value: number) => [value.toLocaleString(), 'Posts']}
                contentStyle={{
                  background: '#F9F8F5',
                  border: '1px solid #D4D1CA',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" fill="#20808D" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Word co-occurrence map */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h3 className="text-sm font-semibold text-text mb-1">Word Co-occurrence Network</h3>
        <p className="text-xs text-text-muted mb-5">Top 25% of unique word pairs within a two-token window across project posts.</p>
        {loading ? (
          <div className="h-56 bg-border/20 rounded animate-pulse" />
        ) : wordMap.edges.length > 0 ? (
          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">Strongest Connections</p>
              <div className="space-y-2">
                {wordMap.edges.slice(0, 10).map((edge) => (
                  <div key={`${edge.source}-${edge.target}`} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2">
                    <span className="text-sm text-text">
                      {edge.source} <span className="text-text-muted">with</span> {edge.target}
                    </span>
                    <span className="text-xs font-semibold text-primary">{edge.count}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">Network Diagram</p>
              <CoOccurrenceNetwork wordMap={wordMap} />
            </div>
          </div>
        ) : (
          <div className="bg-background border border-border rounded-lg p-8 text-center">
            <AlertCircle size={24} className="text-text-muted mx-auto mb-2" />
            <p className="text-sm font-medium text-text">Not enough text for a word map</p>
            <p className="text-xs text-text-muted mt-1">Collect posts for this project to see co-occurrence pairs.</p>
          </div>
        )}
      </div>
    </div>
  )
}
