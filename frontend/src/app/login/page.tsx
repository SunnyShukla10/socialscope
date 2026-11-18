'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Radio, BarChart2, Search, Users, Eye, EyeOff } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#101933] via-[#312E81] to-[#5B21B6] flex-col justify-between p-12 relative overflow-hidden">
        <div aria-hidden="true" className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-cyan-400/20 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -right-24 h-[28rem] w-[28rem] rounded-full bg-violet-400/20 blur-3xl" />
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
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-300/25 to-violet-300/25 border border-white/20 rounded-xl flex items-center justify-center shadow-lg">
            <Radio size={20} className="text-white" />
          </div>
          <div>
            <span className="text-white font-bold text-lg block leading-none">SocialScope</span>
            <span className="text-white/60 text-[10px] font-semibold tracking-widest uppercase">Social listening</span>
          </div>
        </div>

        {/* Feature list */}
        <div className="relative space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight tracking-tight">
            Social listening<br /><span className="text-cyan-200">for academic research</span>
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
                <div className="w-8 h-8 bg-white/10 border border-white/15 rounded-lg flex items-center justify-center text-cyan-200 shrink-0 mt-0.5">
                  {f.icon}
                </div>
                <div>
                  <p className="text-white font-medium text-sm">{f.title}</p>
                  <p className="text-indigo-100/85 text-xs mt-0.5">{f.description}</p>
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
      <div className="flex-1 flex items-center justify-center bg-gradient-to-br from-indigo-50 via-background to-violet-50 p-5 sm:p-8">
        <div className="w-full max-w-md rounded-2xl border border-white bg-surface p-6 shadow-[0_24px_80px_-24px_rgba(49,46,129,0.25)] sm:p-10">
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
              id="login-password"
              className="pr-12"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError('') }}
              placeholder="••••••••"
              autoComplete="current-password"
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(value => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  aria-controls="login-password"
                  className="flex h-8 w-8 items-center justify-center rounded text-text-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                >
                  {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                </button>
              }
              required
            />

            {error && (
              <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                {error}
              </div>
            )}

            <Button
              type="submit"
              loading={loading}
              className="w-full mt-2 bg-gradient-to-r from-primary to-violet-600 shadow-lg shadow-indigo-500/20 hover:from-primary-hover hover:to-violet-700"
              size="lg"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <div className="mt-6 rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
            <p className="text-xs font-semibold text-primary">Pilot access</p>
            <p className="mt-2 text-xs text-text-muted">Use the individual account provided by your research administrator. Contact them if you need access or a password reset.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
