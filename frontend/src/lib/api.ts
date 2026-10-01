// An empty base uses the Next.js same-origin /api proxy. This works from local
// and remote browsers without incorrectly treating the browser as the API host.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''
const visiblePlatforms = (platforms: string[] = []) =>
  platforms.filter((platform) => platform.toLowerCase() !== 'pinterest')

const hidePinterestFromProject = (project: Project): Project => ({
  ...project,
  platforms: visiblePlatforms(project.platforms),
})

// ─── Types ───────────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  full_name?: string
  name: string
  role: string
  organization_id?: string
  created_at: string
}

export interface Project {
  id: string
  name: string
  description: string
  status: 'active' | 'paused' | 'completed' | 'draft'
  post_count: number
  last_activity: string | null
  created_at: string
  updated_at?: string
  query?: string
  platforms?: string[]
  research_question?: string
  boolean_query?: string
  date_from?: string
  date_to?: string
  max_results_per_platform?: number
  owner_id?: string
}

export type SearchJobStatus =
  | 'queued'
  | 'pending'
  | 'running'
  | 'cancelling'
  | 'completed'
  | 'completed_with_errors'
  | 'cancelled'
  | 'failed'

export type PlatformCollectionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'

export interface PlatformCollectionState {
  status: PlatformCollectionStatus
  posts_collected: number
  started_at?: string
  completed_at?: string
  last_progress_at?: string
  error?: string
  provider_stop_reason?: string
  provider_stop_details?: Record<string, unknown>
}

export interface SearchJob {
  id: string
  project_id: string
  query: string
  platforms: string[]
  date_from?: string
  date_to?: string
  max_posts?: number
  platform_allocations: Record<string, number>
  status: SearchJobStatus
  posts_collected: number
  platform_states: Record<string, PlatformCollectionState>
  created_at: string
  started_at?: string
  completed_at?: string
  cancel_requested_at?: string
  cancelled_at?: string
  cancel_requested_by?: string
  last_progress_at?: string
  error_message?: string
}

export interface SearchJobCancellation {
  job_id: string
  status: 'cancelling'
  cancel_requested_at: string
  cancel_requested_by: string
  completed_platforms: string[]
  cancelling_platforms: string[]
}

export interface Post {
  id: string
  project_id: string
  platform: string
  author_username: string
  author_display_name?: string
  author_followers?: number
  content: string
  hashtags: string[]
  likes: number
  comments: number
  shares: number
  views?: number
  url?: string
  published_at: string
  collected_at: string
}

export interface PostFilters {
  platform?: string
  search?: string
  sort?: string
  date_from?: string
  date_to?: string
  page?: number
  limit?: number
}

export interface PaginatedPosts {
  posts: Post[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface AnalyticsOverview {
  total_posts: number
  unique_authors: number
  total_engagement: number
  top_hashtags: number
  posts_delta?: number
  authors_delta?: number
  engagement_delta?: number
}

export interface VolumeDataPoint {
  date: string
  [platform: string]: number | string
}


export interface PlatformDataPoint {
  platform: string
  count: number
  percentage: number
}

export interface HashtagDataPoint {
  hashtag: string
  count: number
}

export interface WordMapNode {
  id: string
  label: string
  count: number
  value?: number
}

export interface WordMapEdge {
  source: string
  target: string
  count: number
  weight?: number
}

export interface WordMapResponse {
  nodes: WordMapNode[]
  edges: WordMapEdge[]
}

interface BackendSearchJob {
  id: string
  project_id: string
  name: string
  status: SearchJobStatus
  platforms: string[]
  date_from?: string | null
  date_to?: string | null
  max_results_per_platform: number
  requested_post_count: number
  platform_allocations: Record<string, number>
  platform_states: Record<string, PlatformCollectionState>
  total_posts_collected: number
  error_message?: string | null
  started_at?: string | null
  completed_at?: string | null
  cancel_requested_at?: string | null
  cancelled_at?: string | null
  cancel_requested_by?: string | null
  last_progress_at?: string | null
  created_at: string
  query_versions?: Array<{ boolean_query: string; is_active: boolean; version_number: number }>
}

export interface QueryCandidate {
  id: string
  query: string
  queryType: 'natural_language' | 'boolean'
  description: string
  estimated_volume?: string
  complexity: 'simple' | 'moderate' | 'complex'
}

export interface ExportRecord {
  id: string
  project_id: string
  format: 'csv' | 'json' | 'xlsx'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  row_count?: number
  file_url?: string
  created_at: string
  completed_at?: string
  options?: Record<string, unknown>
}

interface BackendExportRecord {
  id: string
  project_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  format: 'csv' | 'json' | 'xlsx'
  filters: Record<string, unknown>
  file_path?: string | null
  file_size_bytes?: number | null
  row_count?: number | null
  error_message?: string | null
  created_at: string
  completed_at?: string | null
  download_url?: string | null
}

export interface ApiError {
  message: string
  status: number
  code?: string
  platform?: string
  provider?: string
  actual_length?: number
  maximum_length?: number
}

export interface AnalyticsSourceMixItem {
  platform: string
  post_count: number
  percentage: number
}

export interface AnalyticsTheme {
  name: string
  summary: string
}

export interface AnalyticsTopPosterSummary {
  account_id: string
  username: string
  platform: string
  post_count: number
  total_engagement: number
  summary: string
  topics: string[]
  discussion_style: string
}

export interface AnalyticsSummary {
  status: 'pending' | 'analyzed' | 'failed' | 'empty'
  is_stale: boolean
  total_posts: number
  sampled_posts: number
  source_mix: AnalyticsSourceMixItem[]
  top_poster_share: number
  overview?: string | null
  themes: AnalyticsTheme[]
  top_posters: AnalyticsTopPosterSummary[]
  generated_at?: string | null
  model?: string | null
}

export interface QueryLimits {
  safe_default_maximum_length: number
  warning_ratio: number
  limits_are_official_provider_guarantees: boolean
  providers: Record<string, { maximum_length: number }>
  platforms: Record<string, { provider: string; maximum_length: number }>
}

interface BackendQueryCandidate {
  label: string
  boolean_query: string
  query_type?: 'natural_language' | 'boolean'
  description: string
  or_groups: string[][]
}

interface BackendGenerateQueriesResponse {
  candidates: BackendQueryCandidate[]
  research_question: string
  domain: string
}

interface BackendPost {
  id: string
  project_id: string
  platform: string
  author_username: string | null
  author_display_name?: string | null
  author_followers?: number | null
  body: string
  hashtags: string[]
  likes: number
  comments: number
  shares: number
  views?: number
  url?: string | null
  published_at?: string | null
  collected_at: string
}

interface BackendPaginatedPosts {
  items: BackendPost[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

interface BackendAnalyticsOverview {
  total_posts: number
  unique_authors: number
  platforms_count: number
  top_hashtags: Array<{ tag?: string; hashtag?: string; count: number }>
  total_engagement: number
}

interface BackendVolumeDataPoint {
  date: string
  platform: string
  count: number
}

interface BackendVolumeResponse {
  data: BackendVolumeDataPoint[]
  platforms: string[]
}


interface BackendPlatformDataPoint {
  platform: string
  post_count: number
  total_engagement: number
}

interface BackendPlatformResponse {
  data: BackendPlatformDataPoint[]
}

// ─── Core Fetch ──────────────────────────────────────────────────────────────

export async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('socialscope_token') : null

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('socialscope_token')
      window.location.href = '/login'
    }
    throw { message: 'Unauthorized', status: 401 } as ApiError
  }

  if (!response.ok) {
    let message = `HTTP error ${response.status}`
    let details: Record<string, unknown> = {}
    try {
      const err = await response.json()
      details = typeof err === 'object' && err ? err : {}
      const backendMessage = details.detail || details.message
      message = typeof backendMessage === 'string' ? backendMessage : Array.isArray(backendMessage) ? backendMessage.map((e: {msg?: string}) => e.msg || 'Invalid field').join('; ') : (backendMessage && typeof backendMessage === 'object' && 'message' in backendMessage) ? String(backendMessage.message) : message
    } catch {
      // ignore JSON parse errors
    }
    throw { ...details, message, status: response.status } as ApiError
  }

  // Handle empty responses
  const text = await response.text()
  if (!text) return {} as T
  return JSON.parse(text) as T
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
  return fetchApi('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function getMe(): Promise<User> {
  // Bound the initial session check, including reading its response body.
  // Other API calls may legitimately run longer (for example LLM requests).
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetchApi<User & { full_name?: string }>('/auth/me', {
      signal: controller.signal,
    })
    return {
      ...response,
      name: response.name || response.full_name || response.email,
      created_at: response.created_at || new Date().toISOString(),
    }
  } finally {
    clearTimeout(timeout)
  }
}

// ─── Projects ─────────────────────────────────────────────────────────────────

export async function getProjects(): Promise<Project[]> {
  const projects = await fetchApi<Project[]>('/projects')
  return projects.map(hidePinterestFromProject)
}

export async function getQueryLimits(): Promise<QueryLimits> {
  return fetchApi('/query-limits')
}

export async function getProject(id: string): Promise<Project> {
  return hidePinterestFromProject(await fetchApi<Project>(`/projects/${id}`))
}

export async function createProject(data: {
  name: string
  description: string
  domain?: string
  research_question?: string
  boolean_query?: string
  platforms?: string[]
  date_from?: string
  date_to?: string
  max_results_per_platform?: number
}): Promise<Project> {
  return fetchApi('/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function launchProject(data: {
  name: string
  description: string
  domain?: string
  research_question?: string
  boolean_query?: string
  platforms: string[]
  date_from?: string
  date_to?: string
  max_results_per_platform?: number
  initial_job: {
    name: string
    query: string
    platforms: string[]
    date_from?: string
    date_to?: string
    requested_post_count?: number
    max_results_per_platform?: number
  }
}): Promise<Project> {
  return fetchApi('/projects/launch', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateProject(id: string, data: Partial<Project>): Promise<Project> {
  return fetchApi(`/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// ─── LLM ─────────────────────────────────────────────────────────────────────

export async function deleteProject(id: string): Promise<void> {
  await fetchApi(`/projects/${id}`, {
    method: 'DELETE',
  })
}

export async function generateQueries(
  question: string,
  domain?: string
): Promise<{ candidates: QueryCandidate[] }> {
  const response = await fetchApi<BackendGenerateQueriesResponse>('/llm/generate-queries', {
    method: 'POST',
    body: JSON.stringify({
      research_question: question,
      domain: domain || 'general',
    }),
  })

  return {
    candidates: response.candidates.map((candidate, index) => ({
      id: `q${index + 1}`,
      query: candidate.boolean_query,
      queryType: candidate.query_type || 'boolean',
      description: candidate.description,
      complexity:
        candidate.query_type === 'natural_language' ? 'simple' : index === 1 ? 'moderate' : 'complex',
    })),
  }
}

// ─── Jobs ─────────────────────────────────────────────────────────────────────

export async function createSearchJob(
  projectId: string,
  data: {
    query: string
    platforms: string[]
    date_from?: string
    date_to?: string
    max_posts?: number
  }
): Promise<SearchJob> {
  const response = await fetchApi<BackendSearchJob>(`/projects/${projectId}/jobs`, {
    method: 'POST',
    body: JSON.stringify({
      name: 'Initial collection',
      query: data.query,
      platforms: data.platforms,
      date_from: data.date_from || undefined,
      date_to: data.date_to || undefined,
      requested_post_count: data.max_posts,
      max_results_per_platform: data.max_posts,
    }),
  })
  return normalizeSearchJob(response)
}

export async function getSearchJobs(projectId: string): Promise<SearchJob[]> {
  const response = await fetchApi<BackendSearchJob[]>(`/projects/${projectId}/jobs`)
  return response.map(normalizeSearchJob)
}

export async function cancelSearchJob(
  projectId: string,
  jobId: string
): Promise<SearchJobCancellation> {
  return fetchApi(`/projects/${projectId}/jobs/${jobId}/cancel`, {
    method: 'POST',
  })
}

// ─── Posts ───────────────────────────────────────────────────────────────────

export async function getPosts(projectId: string, filters: PostFilters = {}): Promise<PaginatedPosts> {
  const params = new URLSearchParams()
  if (filters.platform) {
    filters.platform.split(',').filter(Boolean).forEach((platform) => {
      params.append('platform', platform)
    })
  }
  if (filters.search) params.set('search', filters.search)
  if (filters.sort) {
    const sortMap: Record<string, string> = {
      newest: 'newest',
      oldest: 'oldest',
      most_engaged: 'engagement',
    }
    params.set('sort_by', sortMap[filters.sort] || filters.sort)
  }
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.limit) params.set('per_page', String(filters.limit))
  const qs = params.toString()
  const response = await fetchApi<BackendPaginatedPosts>(
    `/projects/${projectId}/posts${qs ? `?${qs}` : ''}`
  )

  return {
    posts: response.items.map((post) => ({
      id: post.id,
      project_id: post.project_id,
      platform: post.platform,
      author_username: post.author_username || 'unknown',
      author_display_name: post.author_display_name || undefined,
      author_followers: post.author_followers || undefined,
      content: post.body,
      hashtags: post.hashtags || [],
      likes: post.likes,
      comments: post.comments,
      shares: post.shares,
      views: post.views,
      url: post.url || undefined,
      published_at: post.published_at || post.collected_at,
      collected_at: post.collected_at,
    })),
    total: response.total,
    page: response.page,
    limit: response.per_page,
    pages: response.total_pages,
  }
}

export async function getAnalyticsOverview(projectId: string): Promise<AnalyticsOverview> {
  const response = await fetchApi<BackendAnalyticsOverview>(`/projects/${projectId}/analytics/overview`)

  return {
    total_posts: response.total_posts,
    unique_authors: response.unique_authors,
    total_engagement: response.total_engagement,
    top_hashtags: response.top_hashtags.length,
  }
}

export async function getAnalyticsVolume(projectId: string): Promise<VolumeDataPoint[]> {
  const response = await fetchApi<BackendVolumeResponse>(`/projects/${projectId}/analytics/volume`)
  const byDate = new Map<string, VolumeDataPoint>()
  const platforms = visiblePlatforms(response.platforms || [])

  response.data
    .filter((point) => point.platform.toLowerCase() !== 'pinterest')
    .forEach((point) => {
    const existing = byDate.get(point.date) || {
      date: point.date,
      ...Object.fromEntries(platforms.map((platform) => [platform, 0])),
    }
    existing[point.platform] = point.count
    byDate.set(point.date, existing)
  })

  return Array.from(byDate.values())
    .map((point) => ({
      date: point.date,
      ...Object.fromEntries(platforms.map((platform) => [platform, Number(point[platform] ?? 0)])),
    }))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
}


export async function getAnalyticsPlatforms(projectId: string): Promise<PlatformDataPoint[]> {
  const response = await fetchApi<BackendPlatformResponse>(`/projects/${projectId}/analytics/platforms`)
  const visibleData = response.data.filter(
    (platform) => platform.platform.toLowerCase() !== 'pinterest'
  )
  const totalPosts = visibleData.reduce((sum, platform) => sum + platform.post_count, 0)

  return visibleData.map((platform) => ({
    platform: platform.platform,
    count: platform.post_count,
    percentage: totalPosts > 0 ? Math.round((platform.post_count / totalPosts) * 100) : 0,
  }))
}

export async function getAnalyticsHashtags(projectId: string): Promise<HashtagDataPoint[]> {
  const response = await fetchApi<BackendAnalyticsOverview>(`/projects/${projectId}/analytics/overview`)

  return response.top_hashtags.map((hashtag) => ({
    hashtag: hashtag.hashtag || hashtag.tag || '',
    count: hashtag.count,
  })).filter((hashtag) => hashtag.hashtag)
}

export async function getAnalyticsWordMap(projectId: string): Promise<WordMapResponse> {
  return fetchApi(`/projects/${projectId}/analytics/wordmap`)
}

export async function getAnalyticsSummary(projectId: string): Promise<AnalyticsSummary> {
  return fetchApi(`/projects/${projectId}/analytics/summary`)
}

export async function refreshAnalyticsSummary(projectId: string): Promise<AnalyticsSummary> {
  return fetchApi(`/projects/${projectId}/analytics/summary/refresh`, { method: 'POST' })
}


export async function createExport(
  projectId: string,
  options: {
    format: 'csv' | 'json' | 'xlsx'
    platform?: string
    date_from?: string
    date_to?: string
  }
): Promise<ExportRecord> {
  const response = await fetchApi<BackendExportRecord>(`/projects/${projectId}/exports`, {
    method: 'POST',
    body: JSON.stringify({
      format: options.format,
      platform: options.platform ? [options.platform] : undefined,
      date_from: options.date_from || undefined,
      date_to: options.date_to || undefined,
    }),
  })

  return normalizeExportRecord(response)
}

export async function getExports(projectId: string): Promise<ExportRecord[]> {
  const response = await fetchApi<BackendExportRecord[]>(`/projects/${projectId}/exports`)
  return response.map(normalizeExportRecord)
}

export async function downloadExport(projectId: string, exportId: string): Promise<Blob> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('socialscope_token') : null
  const headers: Record<string, string> = {}

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}/api/projects/${projectId}/exports/${exportId}/download`, {
    headers,
  })

  if (!response.ok) {
    throw { message: `HTTP error ${response.status}`, status: response.status } as ApiError
  }

  return response.blob()
}

function normalizeExportRecord(exportRecord: BackendExportRecord): ExportRecord {
  return {
    id: exportRecord.id,
    project_id: exportRecord.project_id,
    format: exportRecord.format,
    status: exportRecord.status,
    row_count: exportRecord.row_count || undefined,
    file_url: exportRecord.download_url ? `${API_BASE}${exportRecord.download_url}` : undefined,
    created_at: exportRecord.created_at,
    completed_at: exportRecord.completed_at || undefined,
    options: exportRecord.filters,
  }
}

function normalizeSearchJob(job: BackendSearchJob): SearchJob {
  const activeQuery = job.query_versions
    ?.slice()
    .sort((a, b) => Number(b.is_active) - Number(a.is_active) || b.version_number - a.version_number)
    .find((query) => query.boolean_query)

  return {
    id: job.id,
    project_id: job.project_id,
    query: activeQuery?.boolean_query || job.name,
    platforms: visiblePlatforms(job.platforms || []),
    date_from: job.date_from || undefined,
    date_to: job.date_to || undefined,
    max_posts: job.requested_post_count || job.max_results_per_platform,
    platform_allocations: job.platform_allocations || {},
    status: job.status,
    posts_collected: job.total_posts_collected,
    platform_states: job.platform_states || {},
    error_message: job.error_message || undefined,
    created_at: job.created_at,
    started_at: job.started_at || undefined,
    completed_at: job.completed_at || undefined,
    cancel_requested_at: job.cancel_requested_at || undefined,
    cancelled_at: job.cancelled_at || undefined,
    cancel_requested_by: job.cancel_requested_by || undefined,
    last_progress_at: job.last_progress_at || undefined,
  }
}

// ─── Dashboard Stats ──────────────────────────────────────────────────────────

export interface AdminOverview {
  api_keys: Array<{ key: string; label: string; status: 'present' | 'missing'; masked_value?: string | null }>
  audit_log: Array<{
    id: string
    actor_label: string
    action: string
    target_label?: string | null
    target_type: string
    created_at: string
  }>
}

export async function getAdminOverview(): Promise<AdminOverview> {
  return fetchApi('/admin/overview')
}

function actionLabel(action: string, target?: string) {
  const labels: Record<string, string> = {
    project_created: 'Project created',
    collection_pull_started: 'Collection pull started',
    collection_pull_completed: 'Collection pull completed',
    collection_pull_failed: 'Collection pull failed',
    collection_cancel_requested: 'Collection cancellation requested',
    csv_export_generated: 'CSV export generated',
    admin_settings_changed: 'Admin settings changed',
  }
  return target ? `${labels[action] || action.replaceAll('_', ' ')}: ${target}` : labels[action] || action.replaceAll('_', ' ')
}
