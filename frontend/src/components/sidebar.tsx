'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  FolderOpen,
  Settings,
  LogOut,
  Menu,
  X,
  Radio,
} from 'lucide-react'
import type { User } from '@/lib/api'

interface NavItem {
  href: string
  label: string
  icon: React.ReactNode
}

const navItems: NavItem[] = [
  {
    href: '/dashboard',
    label: 'Dashboard',
    icon: <LayoutDashboard size={18} />,
  },
  {
    href: '/projects',
    label: 'Projects',
    icon: <FolderOpen size={18} />,
  },
  {
    href: '/admin',
    label: 'Admin',
    icon: <Settings size={18} />,
  },
]

interface SidebarProps {
  user?: User | null
}

export function Sidebar({ user }: SidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [mobileOpen, setMobileOpen] = useState(false)

  function handleLogout() {
    localStorage.removeItem('socialscope_token')
    router.push('/login')
  }

  function isActive(href: string) {
    if (href === '/dashboard') return pathname === '/dashboard'
    return pathname.startsWith(href)
  }

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 group"
          onClick={() => setMobileOpen(false)}
        >
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center shrink-0">
            <Radio size={16} className="text-white" />
          </div>
          <div>
            <span className="text-sm font-bold text-text block leading-none">SocialScope</span>
            <span className="text-[10px] font-semibold text-text-muted tracking-widest uppercase leading-none mt-0.5 block">
              Social listening
            </span>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.filter((item) => item.href !== '/admin' || user?.role === 'admin').map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileOpen(false)}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150',
              isActive(item.href)
                ? 'bg-primary/10 text-primary'
                : 'text-text-muted hover:text-text hover:bg-background'
            )}
          >
            <span
              className={cn(
                isActive(item.href) ? 'text-primary' : 'text-text-muted'
              )}
            >
              {item.icon}
            </span>
            {item.label}
          </Link>
        ))}
      </nav>

      {/* User info + logout */}
      <div className="px-3 py-4 border-t border-border space-y-1">
        {user && (
          <div className="px-3 py-2.5 flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center text-xs font-bold text-primary shrink-0">
              {user.name
                ? user.name
                    .split(' ')
                    .map((w) => w[0])
                    .join('')
                    .toUpperCase()
                    .slice(0, 2)
                : 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-text truncate">{user.name}</p>
              <p className="text-xs text-text-muted truncate">{user.email}</p>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-text-muted hover:text-text hover:bg-background transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-60 shrink-0 bg-surface border-r border-border h-screen sticky top-0">
        <SidebarContent />
      </aside>

      {/* Mobile hamburger */}
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-surface border border-border rounded-lg shadow-card"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label="Toggle menu"
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={cn(
          'lg:hidden fixed top-0 left-0 h-full w-72 bg-surface border-r border-border z-50 transition-transform duration-300',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <SidebarContent />
      </aside>
    </>
  )
}
