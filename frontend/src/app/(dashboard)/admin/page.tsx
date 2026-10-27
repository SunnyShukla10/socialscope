'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminOverview, type AdminOverview } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PilotAdmin } from '@/components/pilot-admin'
import { Key, Shield } from 'lucide-react'

export default function AdminPage() {
  const router = useRouter()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [denied, setDenied] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getAdminOverview()
      .then(setOverview)
      .catch((error) => {
        if (error?.status === 403) setDenied(true)
        else setError(error?.message || 'Could not load admin information. Please refresh to retry.')
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

  if (error) return <div className="p-6 text-sm text-red-600" role="alert">{error}</div>

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

      <PilotAdmin />
    </div>
  )
}
