'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { deleteProject, getProjects, type Project } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.description || '').toLowerCase().includes(searchQuery.toLowerCase())
  )

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
    <div className="p-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-text">Projects</h2>
          <p className="text-text-muted text-sm mt-1">
            {projects.length} project{projects.length !== 1 ? 's' : ''} total
          </p>
        </div>
        <Link href="/projects/new">
          <Button>
            <Plus size={16} />
            New Project
          </Button>
        </Link>
      </div>

      {/* Search */}
      {!loading && projects.length > 0 && (
        <div className="mb-5 max-w-sm">
          <Input
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search size={15} />}
          />
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
      ) : filtered.length === 0 && searchQuery ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <Search size={32} className="text-border mx-auto mb-3" />
          <p className="text-sm font-medium text-text mb-1">No projects match "{searchQuery}"</p>
          <button
            onClick={() => setSearchQuery('')}
            className="text-xs text-primary hover:text-primary-hover transition-colors"
          >
            Clear search
          </button>
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-12 text-center max-w-md mx-auto">
          <div className="w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center mx-auto mb-4">
            <FolderOpen size={24} className="text-primary" />
          </div>
          <h3 className="text-base font-semibold text-text mb-2">Create your first project</h3>
          <p className="text-sm text-text-muted mb-6">
            Projects help you organize your social listening campaigns. Define your research question and we'll help you collect the right data.
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
              className="group bg-surface border border-border rounded-lg p-5 hover:shadow-card-hover transition-all duration-200"
            >
              {/* Card header */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <Link href={`/projects/${project.id}`} className="min-w-0">
                  <h3 className="text-sm font-semibold text-text leading-snug group-hover:text-primary transition-colors line-clamp-2">
                    {project.name}
                  </h3>
                </Link>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Badge variant={statusVariant[project.status] || 'muted'}>
                    {project.status}
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
                <p className="text-xs text-text-muted leading-relaxed mb-4 line-clamp-2">
                  {project.description}
                </p>

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
                  <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-border/60">
                    {project.platforms.slice(0, 4).map((p) => (
                      <div
                        key={p}
                        className="w-5 h-5 rounded-full bg-border/50 flex items-center justify-center"
                        title={p}
                      >
                        <span className="text-[10px] font-bold text-text-muted uppercase">
                          {p[0]}
                        </span>
                      </div>
                    ))}
                    {project.platforms.length > 4 && (
                      <span className="text-xs text-text-muted">+{project.platforms.length - 4}</span>
                    )}
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
