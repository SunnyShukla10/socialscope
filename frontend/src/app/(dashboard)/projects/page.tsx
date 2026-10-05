'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { deleteProject, getProjects, type Project } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PlatformBadge } from '@/components/platform-badge'
import { label } from '@/lib/research'
import { field } from '@/components/research-ui'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { formatNumber, formatRelativeTime } from '@/lib/utils'
import {
  Plus,
  FolderOpen,
  Database,
  Clock,
  Search,
  AlertCircle,
  Activity,
  ArrowRight,
  Trash2,
} from 'lucide-react'

const statusVariant: Record<string, 'success' | 'info' | 'muted' | 'warning' | 'danger'> = {
  active: 'success',
  completed: 'info',
  draft: 'muted',
  paused: 'warning',
}

export default function ProjectsPage() {
  const { addToast } = useToast()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [status, setStatus] = useState('')
  const [platform, setPlatform] = useState('')
  const [sort, setSort] = useState('recent')
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    getProjects()
      .then(setProjects)
      .catch(() => {
        setProjects([])
        setError('Failed to load projects.')
      })
      .finally(() => setLoading(false))
  }, [])

  const availablePlatforms = Array.from(new Set(projects.flatMap(p => p.platforms || []))).sort()
  const hasFilters = Boolean(searchQuery || status || platform)
  const clearFilters = () => { setSearchQuery(''); setStatus(''); setPlatform('') }
  const filtered = projects.filter(p =>
    [p.name, p.description, p.research_question, p.boolean_query, p.query].some(value =>
      (value || '').toLowerCase().includes(searchQuery.trim().toLowerCase())) &&
    (!status || p.status === status) && (!platform || p.platforms?.includes(platform))
  ).sort((a, b) => {
    if (sort === 'name') return a.name.localeCompare(b.name)
    if (sort === 'posts') return b.post_count - a.post_count || a.name.localeCompare(b.name)
    const timestamp = (p: Project) => Date.parse(sort === 'newest' ? p.created_at : p.last_activity || p.updated_at || p.created_at) || 0
    return timestamp(b) - timestamp(a)
  })

  async function handleDeleteProject() {
    if (!projectToDelete) return
    setDeleting(true)
    try {
      await deleteProject(projectToDelete.id)
      setProjects((prev) => prev.filter((project) => project.id !== projectToDelete.id))
      addToast('Project and associated data deleted.', 'success')
      setProjectToDelete(null)
    } catch {
      addToast('Failed to delete project. Please try again.', 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="mx-auto p-4 sm:p-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-3xl font-bold text-text">Projects</h2>
          <p className="text-text-muted text-sm mt-1">
            Your conversations, organized by topic.
          </p>
        </div>
        <Link href="/projects/new">
          <Button>
            <Plus size={16} />
            New Project
          </Button>
        </Link>
      </div>

      {!loading && !error && projects.length > 0 && (
        <div className="mb-6 space-y-3 rounded-xl border border-border bg-surface p-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr]">
            <Input aria-label="Search projects" placeholder="Search projects or queries" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} leftIcon={<Search size={15} />} />
            <select aria-label="Filter by status" className={field} value={status} onChange={e => setStatus(e.target.value)}>
              <option value="">All statuses</option>{Object.keys(statusVariant).map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
            <select aria-label="Filter by platform" className={field} value={platform} onChange={e => setPlatform(e.target.value)}>
              <option value="">All platforms</option>{availablePlatforms.map(p => <option key={p} value={p}>{label(p)}</option>)}
            </select>
            <select aria-label="Sort projects" className={field} value={sort} onChange={e => setSort(e.target.value)}>
              <option value="recent">Recently active</option><option value="newest">Newest created</option><option value="name">Name A-Z</option><option value="posts">Most posts</option>
            </select>
          </div>
          <div className="flex items-center justify-between gap-3 text-xs text-text-muted">
            <span role="status">{filtered.length} of {projects.length} projects</span>
            {hasFilters && <button className="font-medium text-primary" onClick={clearFilters}>Clear filters</button>}
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-surface border border-border rounded-lg p-5 animate-pulse">
              <div className="flex items-start justify-between mb-3">
                <div className="h-5 bg-border/60 rounded w-40" />
                <div className="h-5 bg-border/60 rounded w-16" />
              </div>
              <div className="h-4 bg-border/60 rounded w-full mb-1.5" />
              <div className="h-4 bg-border/60 rounded w-3/4 mb-5" />
              <div className="flex gap-3">
                <div className="h-3.5 bg-border/60 rounded w-20" />
                <div className="h-3.5 bg-border/60 rounded w-24" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
          <p className="text-sm font-medium text-text mb-1">Failed to load projects</p>
          <p className="text-xs text-text-muted">{error}</p>
        </div>
      ) : filtered.length === 0 && hasFilters ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <Search size={32} className="text-border mx-auto mb-3" />
          <p className="text-sm font-medium text-text mb-1">No projects match these filters</p>
          <button
            onClick={clearFilters}
            className="text-xs text-primary hover:text-primary-hover transition-colors"
          >
            Clear filters
          </button>
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-12 text-center max-w-md mx-auto">
          <div className="w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center mx-auto mb-4">
            <FolderOpen size={24} className="text-primary" />
          </div>
          <h3 className="text-base font-semibold text-text mb-2">Create your first project</h3>
          <p className="text-sm text-text-muted mb-6">
            Choose a topic and start collecting conversations.
          </p>
          <Link href="/projects/new">
            <Button>
              <Plus size={16} />
              New Project
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((project) => (
            <div
              key={project.id}
              className="group bg-surface border border-border rounded-xl p-5 hover:border-primary/40 hover:shadow-card-hover transition-all duration-200"
            >
              {/* Card header */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <Link href={`/projects/${project.id}`} className="min-w-0">
                  <h3 className="text-base font-semibold text-text leading-snug group-hover:text-primary transition-colors line-clamp-2">
                    {project.name}
                  </h3>
                </Link>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Badge variant={statusVariant[project.status] || 'muted'}>
                    {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
                  </Badge>
                  <button
                    type="button"
                    title="Delete project"
                    aria-label={`Delete ${project.name}`}
                    onClick={() => setProjectToDelete(project)}
                    className="p-1.5 rounded text-text-muted hover:text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              <Link href={`/projects/${project.id}`} className="block">
                {/* Description */}
                {(project.research_question || project.description) && <p className="text-sm text-text-muted leading-relaxed mb-4 line-clamp-2">
                  {project.research_question || project.description}
                </p>}
                {(project.boolean_query || project.query) && <p className="mb-4 truncate rounded-lg bg-background px-3 py-2 font-mono text-xs text-text-muted" title={project.boolean_query || project.query}>{project.boolean_query || project.query}</p>}

                {/* Stats */}
                <div className="flex items-center gap-4 text-xs text-text-muted">
                  <span className="flex items-center gap-1">
                    <Database size={12} />
                    {formatNumber(project.post_count)} posts
                  </span>
                  {project.last_activity ? (
                    <span className="flex items-center gap-1">
                      <Clock size={12} />
                      {formatRelativeTime(project.last_activity)}
                    </span>
                  ) : project.status === 'draft' ? (
                    <span className="flex items-center gap-1">
                      <Activity size={12} />
                      Not started
                    </span>
                  ) : null}
                </div>

                {/* Platform tags */}
                {project.platforms && project.platforms.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 mt-4 pt-3 border-t border-border/60">
                    {project.platforms.map(p => <PlatformBadge key={p} platform={p} />)}
                    <ArrowRight
                      size={14}
                      className="ml-auto text-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </div>
                )}
              </Link>
            </div>
          ))}
        </div>
      )}

      <Dialog
        open={!!projectToDelete}
        onClose={() => {
          if (!deleting) setProjectToDelete(null)
        }}
        title="Delete Project"
        description="This will permanently delete the project and its collected data."
      >
        <DialogContent>
          <p className="text-sm text-text">
            Delete <span className="font-semibold">{projectToDelete?.name}</span>?
          </p>
          <p className="text-sm text-text-muted mt-2">
            Associated runs, posts, provenance, usage records, exports, and project activity will be removed.
          </p>
        </DialogContent>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setProjectToDelete(null)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDeleteProject}
            loading={deleting}
          >
            <Trash2 size={15} />
            Delete
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  )
}
