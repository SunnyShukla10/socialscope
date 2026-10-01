'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminOverview, type AdminOverview } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatRelativeTime } from '@/lib/utils'
import { AlertCircle, Key, Shield } from 'lucide-react'

export default function AdminPage() {
  const router = useRouter()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [denied, setDenied] = useState(false)

  useEffect(() => {
    getAdminOverview()
      .then(setOverview)
      .catch((error) => {
        if (error?.status === 403) setDenied(true)
      })
      .finally(() => setLoading(false))
  }, [])

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

  return (
    <div className="p-6 max-w-6xl space-y-6">
      <section className="bg-surface border border-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-1">
          <Key size={16} className="text-primary" />
          <h2 className="text-base font-semibold text-text">API Configuration</h2>
        </div>
        <p className="text-sm text-text-muted mb-5">Server-side credential status. Secret values are masked.</p>
        <div className="grid md:grid-cols-3 gap-3">
          {(overview?.api_keys || []).map((key) => (
            <div key={key.key} className="border border-border rounded-lg bg-background p-4">
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
      </section>

      <section className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-base font-semibold text-text">Audit log</h2>
        <p className="text-sm text-text-muted mt-1 mb-5">
          Every research, comparison, ingestion, export, and annotation event in this workspace.
        </p>
        {overview?.audit_log.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs font-semibold text-text-muted">
                  <th className="py-2 pr-4">Time</th>
                  <th className="py-2 pr-4">Actor</th>
                  <th className="py-2 pr-4">Action</th>
                  <th className="py-2 pr-4">Target</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {overview.audit_log.map((event) => (
                  <tr key={event.id}>
                    <td className="py-3 pr-4 text-text-muted whitespace-nowrap">{formatRelativeTime(event.created_at)}</td>
                    <td className="py-3 pr-4 text-text">{event.actor_label}</td>
                    <td className="py-3 pr-4">
                      <Badge variant="info">{event.action.replaceAll('_', ' ')}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-text">{event.target_label || event.target_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-background border border-border rounded-lg p-8 text-center">
            <AlertCircle size={24} className="text-text-muted mx-auto mb-2" />
            <p className="text-sm font-medium text-text">No audit events yet</p>
            <p className="text-xs text-text-muted mt-1">Create projects, start pulls, flag candidates, or export CSVs to populate the log.</p>
          </div>
        )}
      </section>
    </div>
  )
}
