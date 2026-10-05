'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Radio, BarChart2, Search, Users } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Redirect if already logged in
  useEffect(() => {
    const token = localStorage.getItem('socialscope_token')
    if (token) router.push('/dashboard')
  }, [router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (!email.trim() || !password.trim()) {
      setError('Please enter your email and password.')
      return
    }

    setLoading(true)
    try {
      const result = await login(email.trim(), password)
      localStorage.setItem('socialscope_token', result.access_token)
      router.push('/dashboard')
    } catch (err: unknown) {
      const apiErr = err as { message?: string }
      setError(apiErr?.message || 'Invalid email or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#01696F] to-[#1B474D] flex-col justify-between p-12 relative overflow-hidden">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>
        </div>

        {/* Logo */}
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
            <Radio size={20} className="text-white" />
          </div>
          <div>
            <span className="text-white font-bold text-lg block leading-none">SocialScope</span>
            <span className="text-white/60 text-[10px] font-semibold tracking-widest uppercase">Social listening</span>
          </div>
        </div>

        {/* Feature list */}
        <div className="relative space-y-6">
          <h1 className="text-3xl font-bold text-white leading-tight">
            Social listening<br />for academic research
          </h1>
          <div className="space-y-4">
            {[
              {
                icon: <Search size={18} />,
                title: 'Search & collect',
                description: 'Find conversations across your social platforms',
              },
              {
                icon: <BarChart2 size={18} />,
                title: 'Descriptive analytics',
                description: 'Volume trends, platform breakdowns, and keyword patterns',
              },
              {
                icon: <Users size={18} />,
                title: 'Research datasets',
                description: 'Review, exclude, restore, and export collected posts',
              },
            ].map((f) => (
              <div key={f.title} className="flex items-start gap-3">
                <div className="w-8 h-8 bg-white/15 rounded-lg flex items-center justify-center text-white shrink-0 mt-0.5">
                  {f.icon}
                </div>
                <div>
                  <p className="text-white font-medium text-sm">{f.title}</p>
                  <p className="text-white/60 text-xs mt-0.5">{f.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-white/40 text-xs">
          © 2026 SocialScope. All rights reserved.
        </p>
      </div>

      {/* Right panel — login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="w-9 h-9 bg-primary rounded-lg flex items-center justify-center">
              <Radio size={18} className="text-white" />
            </div>
            <div>
              <span className="text-text font-bold text-base block leading-none">SocialScope</span>
              <span className="text-text-muted text-[10px] font-semibold tracking-widest uppercase">Social listening</span>
            </div>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-text">Welcome back</h2>
            <p className="text-text-muted text-sm mt-1.5">Sign in to your account to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError('') }}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError('') }}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                {error}
              </div>
            )}

            <Button
              type="submit"
              loading={loading}
              className="w-full mt-2"
              size="lg"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <div className="mt-6 rounded-lg border border-primary/15 bg-primary/6 p-4">
            <p className="text-xs font-semibold text-primary">Pilot access</p>
            <p className="mt-2 text-xs text-text-muted">Use the account provided by your research administrator. For a local installation, use the login values generated by setup in your private configuration file.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
