export function distribution(platforms: string[], total: number, overrides?: Record<string, number>): {
  percentages: Record<string, number>; counts: Record<string, number>; error: string
}
