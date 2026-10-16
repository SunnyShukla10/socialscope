const weights = {twitter: 0.05, reddit: 0.05, youtube: 0.05, instagram: 0.8, tiktok: 1.75, facebook: 0.5}

export function distribution(platforms, total, overrides = {}) {
  const fixed = Object.values(overrides).reduce((sum, n) => sum + n, 0)
  const automatic = platforms.filter(p => !(p in overrides))
  const error = Object.values(overrides).some(n => !Number.isFinite(n) || n < 0 || n > 100)
    ? 'Enter percentages between 0 and 100.'
    : fixed > 100 + 1e-8 ? 'Your percentages exceed 100%. Lower a share to continue.'
    : !automatic.length && platforms.length && Math.abs(fixed - 100) > 1e-8
    ? 'Percentages must total 100%, or clear a field to use automatic distribution.' : ''
  if (!platforms.length || error) return {percentages: {}, counts: {}, error}
  const automaticWeight = automatic.reduce((sum, p) => sum + (weights[p] ?? 1), 0)
  const custom = Object.keys(overrides).length > 0
  const allocationWeights = Object.fromEntries(platforms.map(p => [p, custom
    ? overrides[p] ?? (Math.max(0, 100 - fixed) * (weights[p] ?? 1) / automaticWeight)
    : weights[p] ?? 1]))
  const totalWeight = Object.values(allocationWeights).reduce((sum, n) => sum + n, 0)
  const percentages = Object.fromEntries(platforms.map(p => [p, 100 * allocationWeights[p] / totalWeight]))
  const raw = Object.fromEntries(platforms.map(p => [p, total * allocationWeights[p] / totalWeight]))
  const counts = Object.fromEntries(platforms.map(p => [p, Math.floor(raw[p])]))
  const remainder = total - Object.values(counts).reduce((sum, n) => sum + n, 0)
  const order = [...platforms].sort((a, b) =>
    (raw[b] - counts[b]) - (raw[a] - counts[a]) || percentages[b] - percentages[a] || b.localeCompare(a))
  for (const p of order.slice(0, remainder)) counts[p]++
  return {percentages, counts, error}
}
