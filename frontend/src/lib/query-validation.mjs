export const DEFAULT_QUERY_LIMITS = {
  safe_default_maximum_length: 200,
  warning_ratio: 0.8,
  limits_are_official_provider_guarantees: false,
  providers: {
    xpoz: { maximum_length: 200 },
    socialvault: { maximum_length: 200 },
  },
  platforms: {
    twitter: { provider: 'xpoz', maximum_length: 200 },
    instagram: { provider: 'xpoz', maximum_length: 200 },
    reddit: { provider: 'socialvault', maximum_length: 200 },
    tiktok: { provider: 'socialvault', maximum_length: 200 },
    youtube: { provider: 'socialvault', maximum_length: 200 },
    facebook: { provider: 'socialvault', maximum_length: 200 },
    pinterest: { provider: 'socialvault', maximum_length: 200 },
  },
}

const PLATFORM_NAMES = {
  twitter: 'Twitter / X',
  instagram: 'Instagram',
  reddit: 'Reddit',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  facebook: 'Facebook',
  pinterest: 'Pinterest',
}

const PROVIDER_NAMES = {
  xpoz: 'Xpoz',
  socialvault: 'SociaVault',
  unknown: 'Unknown provider',
}

export function characterCount(value) {
  return Array.from(value).length
}

function platformContext(platform, limits) {
  const normalized = platform.toLowerCase()
  const configured = limits.platforms[normalized]
  return {
    platform: normalized,
    provider: configured?.provider || 'unknown',
    maximum_length:
      configured?.maximum_length || limits.safe_default_maximum_length,
  }
}

export function applicableMaximum(platforms, limits = DEFAULT_QUERY_LIMITS) {
  const contexts = platforms.map((platform) => platformContext(platform, limits))
  if (contexts.length === 0) return limits.safe_default_maximum_length
  return Math.min(...contexts.map((context) => context.maximum_length))
}

function syntaxErrorCode(query) {
  if (!query.trim()) return 'MALFORMED_BOOLEAN_QUERY'
  let inQuote = false
  let escaped = false
  let depth = 0
  const outsideQuotes = []

  for (const character of query) {
    if (escaped) {
      escaped = false
      if (!inQuote) outsideQuotes.push(character)
      continue
    }
    if (character === '\\') {
      escaped = true
      if (!inQuote) outsideQuotes.push(character)
      continue
    }
    if (character === '"') {
      inQuote = !inQuote
      outsideQuotes.push(' ')
      continue
    }
    if (inQuote) {
      outsideQuotes.push(' ')
      continue
    }
    outsideQuotes.push(character)
    if (character === '(') depth += 1
    if (character === ')') {
      depth -= 1
      if (depth < 0) return 'UNBALANCED_PARENTHESES'
    }
  }

  if (inQuote) return 'UNBALANCED_QUOTES'
  if (depth !== 0) return 'UNBALANCED_PARENTHESES'

  const booleanText = outsideQuotes.join('')
  if (booleanText.includes('&&') || booleanText.includes('||')) {
    return 'UNSUPPORTED_BOOLEAN_OPERATOR'
  }
  if (/^\s*(?:AND|OR)\b/.test(booleanText)) return 'MALFORMED_BOOLEAN_QUERY'
  if (/\b(?:AND|OR|NOT)\s*$/.test(booleanText)) return 'MALFORMED_BOOLEAN_QUERY'
  if (/\b(?:AND|OR)\s+(?:AND|OR)\b/.test(booleanText)) return 'MALFORMED_BOOLEAN_QUERY'
  if (/\bNOT\s+(?:AND|OR)\b/.test(booleanText)) return 'MALFORMED_BOOLEAN_QUERY'
  if (/\(\s*\)/.test(booleanText)) return 'MALFORMED_BOOLEAN_QUERY'
  return null
}

function issueMessage(code, context, actualLength) {
  const platformName = PLATFORM_NAMES[context.platform] || context.platform || 'Selected platform'
  const providerName = PROVIDER_NAMES[context.provider] || context.provider
  if (code === 'QUERY_TOO_LONG') {
    return (
      `${platformName} via ${providerName} is configured for queries up to ` +
      `${context.maximum_length} characters; this query has ${actualLength}. ` +
      'Shorten the query without changing its intended meaning.'
    )
  }
  if (code === 'UNBALANCED_PARENTHESES') {
    return `The query has unbalanced parentheses for ${platformName} via ${providerName}.`
  }
  if (code === 'UNBALANCED_QUOTES') {
    return `The query has an unbalanced double quote for ${platformName} via ${providerName}.`
  }
  if (code === 'UNSUPPORTED_BOOLEAN_OPERATOR') {
    return `${platformName} via ${providerName} does not accept && or || here. Use the words AND or OR.`
  }
  return `The Boolean query is malformed for ${platformName} via ${providerName}.`
}

export function validateFrontendQuery(query, platforms, limits = DEFAULT_QUERY_LIMITS) {
  const contexts = platforms.length
    ? platforms.map((platform) => platformContext(platform, limits))
    : [{
        platform: '',
        provider: 'unknown',
        maximum_length: limits.safe_default_maximum_length,
      }]
  const actualLength = characterCount(query)
  const exceeded = contexts
    .filter((context) => actualLength > context.maximum_length)
    .sort((left, right) => left.maximum_length - right.maximum_length)

  if (exceeded.length) {
    const context = exceeded[0]
    return {
      code: 'QUERY_TOO_LONG',
      ...context,
      actual_length: actualLength,
      message: issueMessage('QUERY_TOO_LONG', context, actualLength),
    }
  }

  const code = syntaxErrorCode(query)
  if (!code) return null
  const context = contexts[0]
  return {
    code,
    ...context,
    actual_length: actualLength,
    message: issueMessage(code, context, actualLength),
  }
}
