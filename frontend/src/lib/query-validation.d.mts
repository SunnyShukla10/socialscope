export interface QueryPlatformLimit {
  provider: string
  maximum_length: number
}

export interface QueryLimits {
  safe_default_maximum_length: number
  warning_ratio: number
  limits_are_official_provider_guarantees: boolean
  providers: Record<string, { maximum_length: number }>
  platforms: Record<string, QueryPlatformLimit>
}

export interface FrontendQueryIssue extends QueryPlatformLimit {
  code: string
  platform: string
  actual_length: number
  message: string
}

export const DEFAULT_QUERY_LIMITS: QueryLimits
export function characterCount(value: string): number
export function applicableMaximum(platforms: string[], limits?: QueryLimits): number
export function validateFrontendQuery(
  query: string,
  platforms: string[],
  limits?: QueryLimits
): FrontendQueryIssue | null
