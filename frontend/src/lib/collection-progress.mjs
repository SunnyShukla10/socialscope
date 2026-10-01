const TERMINAL_PLATFORM_STATUSES = new Set(['completed', 'failed', 'cancelled'])
const TERMINAL_JOB_STATUSES = new Set([
  'completed',
  'completed_with_errors',
  'cancelled',
  'failed',
])

export function findPlatformState(platform, platformStates = {}) {
  const normalized = platform.toLowerCase()
  return platformStates[normalized] || platformStates[platform] || null
}

export function platformProgress(platforms = [], platformStates = {}, overallStatus = '') {
  const uniquePlatforms = [...new Set(platforms.map((platform) => platform.toLowerCase()))]
  const overallIsTerminal = TERMINAL_JOB_STATUSES.has(overallStatus)
  const finished = uniquePlatforms.filter((platform) => {
    const state = findPlatformState(platform, platformStates)
    return state
      ? TERMINAL_PLATFORM_STATUSES.has(state.status)
      : overallIsTerminal
  }).length
  const total = uniquePlatforms.length

  return {
    finished,
    total,
    percent: total === 0 ? 0 : Math.round((finished / total) * 100),
  }
}

export function displayPlatformState(platform, platformStates = {}, overallStatus = '') {
  const state = findPlatformState(platform, platformStates)
  if (state) return state
  if (TERMINAL_JOB_STATUSES.has(overallStatus)) {
    return { status: 'unavailable', posts_collected: 0 }
  }
  return { status: 'pending', posts_collected: 0 }
}

export function shortProviderError(error, maximumLength = 120) {
  if (!error) return ''
  const singleLine = String(error).replace(/\s+/g, ' ').trim()
  if (singleLine.length <= maximumLength) return singleLine
  return `${singleLine.slice(0, maximumLength - 3).trimEnd()}...`
}
