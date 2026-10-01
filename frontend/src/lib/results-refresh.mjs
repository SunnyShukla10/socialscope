const ACTIVE_COLLECTION_STATUSES = new Set([
  'queued',
  'pending',
  'running',
  'cancelling',
])

export function isCollectionActive(status) {
  return ACTIVE_COLLECTION_STATUSES.has(status)
}

export function latestSearchJob(jobs = []) {
  if (jobs.length === 0) return null
  return jobs.reduce((latest, job) => (
    new Date(job.created_at).getTime() > new Date(latest.created_at).getTime()
      ? job
      : latest
  ))
}

export function hasCommittedPostIncrease(previous, currentJob) {
  if (!previous || !currentJob || previous.jobId !== currentJob.id) return false
  return currentJob.posts_collected > previous.postsCollected
}

export function resultRefreshMode(page) {
  return page === 1 ? 'full' : 'summary'
}
