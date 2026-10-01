'use client'

import React, { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { Sidebar } from '@/components/sidebar'
import { getMe, type User } from '@/lib/api'

function getPageTitle(pathname: string): string {
  if (pathname === '/dashboard') return 'Dashboard'
  if (pathname === '/admin') return 'Admin'
  if (pathname === '/projects') return 'Projects'
  if (pathname === '/projects/new') return 'New Project'
  if (pathname.match(/^\/projects\/[^/]+\/collections/)) return 'Collections'
  if (pathname.match(/^\/projects\/[^/]+\/results/)) return 'Results'
  if (pathname.match(/^\/projects\/[^/]+\/analytics/)) return 'Analytics'
  if (pathname.match(/^\/projects\/[^/]+\/export/)) return 'Export'
  if (pathname.match(/^\/projects\/[^/]+/)) return 'Project'
  return 'SocialScope'
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [connectionError, setConnectionError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setConnectionError(false)
    const token = localStorage.getItem('socialscope_token')
    if (!token) {
      router.push('/login')
      return
    }
    getMe()
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch((error) => {
        // fetchApi handles confirmed expired sessions (401). Network/server
        // failures should allow retrying without throwing away the token.
        if (active && error?.status !== 401) setConnectionError(true)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [router, attempt])

  if (connectionError) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div role="alert" className="text-center flex flex-col items-center gap-3">
          <h1 className="text-lg font-semibold">Unable to connect</h1>
          <p className="text-sm text-text-muted">We couldn’t verify your session. Please check your connection and try again.</p>
          <button
            type="button"
            className="rounded-lg bg-primary px-4 py-2 text-white"
            onClick={() => { setConnectionError(false); setLoading(true); setAttempt((value) => value + 1) }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (loading || !user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-muted">Loading...</p>
        </div>
      </div>
    )
  }

  const pageTitle = getPageTitle(pathname)

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar user={user} />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-surface border-b border-border px-6 py-4 flex items-center justify-between shrink-0 lg:pl-6 pl-16">
          <h1 className="text-base font-semibold text-text">{pageTitle}</h1>
          {user && (
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center text-xs font-bold text-primary">
                {user.name
                  ? user.name
                      .split(' ')
                      .map((w) => w[0])
                      .join('')
                      .toUpperCase()
                      .slice(0, 2)
                  : 'U'}
              </div>
              <span className="text-sm text-text-muted hidden sm:block">{user.name}</span>
            </div>
          )}
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
