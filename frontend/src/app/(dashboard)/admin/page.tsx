'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminOverview, type AdminOverview } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AdminWorkspace } from '@/components/admin-workspace'
import { Key, RefreshCw, Shield } from 'lucide-react'

export default function AdminPage() {
  const router = useRouter()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [denied, setDenied] = useState(false)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    let active = true
    setRefreshing(true)
    setError('')
    getAdminOverview()
      .then(value => { if (active) setOverview(value) })
      .catch((error) => {
        if (!active) return
        if (error?.status === 403) setDenied(true)
        else setError(error?.message || 'Could not load admin information. Please refresh to retry.')
      })
      .finally(() => { if (active) { setLoading(false); setRefreshing(false) } })
    return () => { active = false }
  }, [refreshKey])

  if (loading) {
    return (
      <div className="p-6">
        <div className="h-8 bg-border/60 rounded w-48 mb-4 animate-pulse" />
        <div className="h-64 bg-border/30 rounded-xl animate-pulse" />
      </div>
    )
  }

  if (denied) {
    return (
      <div className="p-6 max-w-xl">
        <div className="bg-surface border border-border rounded-xl p-8 text-center">
          <Shield size={32} className="text-text-muted mx-auto mb-3" />
          <h2 className="text-base font-semibold text-text mb-1">Access denied</h2>
          <p className="text-sm text-text-muted mb-4">Admin credentials are required for configuration and audit logs.</p>
          <Button variant="outline" onClick={() => router.push('/dashboard')}>Back to Dashboard</Button>
        </div>
      </div>
    )
  }

  if (error && !overview) return <div className="space-y-3 p-6"><p className="text-sm text-red-600" role="alert">{error}</p><Button variant="outline" disabled={refreshing} onClick={() => setRefreshKey(value => value + 1)}>Retry</Button></div>

  return (
    <div className="min-w-0 max-w-6xl space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><div className="rounded-xl bg-gradient-to-br from-primary to-violet-600 p-2.5 text-white"><Shield size={20} aria-hidden="true" /></div>
          <div><h1 className="text-xl font-semibold tracking-tight text-text">Administration</h1><p className="mt-1 text-xs text-text-muted">Manage access and keep track of your organization.</p></div>
        </div>
      </div>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <details className="rounded-xl border border-border bg-surface shadow-card">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-text"><span className="inline-flex items-center gap-2"><Key size={15} className="text-primary" aria-hidden="true" />Provider connections <span className="text-xs font-normal text-text-muted">{(overview?.api_keys || []).filter(key => key.status === 'present').length} / {(overview?.api_keys || []).length} configured</span></span></summary>
        <div className="border-t border-border p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-text-muted">Server-side credential status. No secret values are displayed.</p><Button size="sm" variant="outline" disabled={refreshing} onClick={() => setRefreshKey(value => value + 1)}><RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} aria-hidden="true" />Refresh connections</Button></div>
        <div className="grid gap-3 md:grid-cols-3">
          {(overview?.api_keys || []).map((key) => (
            <div key={key.key} className="border border-border rounded-lg bg-background p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-text">{key.label}</p>
                <Badge variant={key.status === 'present' ? 'success' : 'muted'}>
                  {key.status}
                </Badge>
              </div>
              <p className="text-xs font-mono text-text-muted mt-2">{key.masked_value || 'Not configured'}</p>
            </div>
          ))}
        </div>
        </div>
      </details>

      <AdminWorkspace />
    </div>
  )
}
