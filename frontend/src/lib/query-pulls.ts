import type { Run } from './research'

export function queryPulls(runs: Run[]) {
  const groups = new Map<string, Run[]>()
  const ordered = [...runs].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id.localeCompare(b.id))
  for (const run of ordered) {
    const id = run.pull_id || run.id
    groups.set(id, [...(groups.get(id) || []), run])
  }
  return Array.from(groups, ([id, entries], index) => {
    const latest = entries[entries.length - 1]
    return {
      id, entries, latest, number: index + 1,
      query: latest.query_versions[0]?.boolean_query || latest.name,
      platforms: Array.from(new Set(entries.flatMap(run => run.platforms))),
      resultRun: [...entries].reverse().find(run => run.mode === 'collection') || latest,
    }
  }).sort((a, b) => Date.parse(b.latest.created_at) - Date.parse(a.latest.created_at) || b.number - a.number)
}

export const pullAnchor = (id: string) => `pull-${id}`
