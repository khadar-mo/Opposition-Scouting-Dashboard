import type { PassEdge, PassNode } from '../api'

export interface CombinedEdge {
  a: PassNode
  b: PassNode
  total: number
  ab: number
  ba: number
}

/** Merge directed pass counts into one undirected edge per pair (drawn once). */
export function combineEdges(nodes: PassNode[], edges: PassEdge[]): CombinedEdge[] {
  const byId = new Map(nodes.map((n) => [n.player_id, n]))
  const seen = new Map<string, CombinedEdge>()
  for (const e of edges) {
    const a = byId.get(Math.min(e.passer_id, e.receiver_id))
    const b = byId.get(Math.max(e.passer_id, e.receiver_id))
    if (!a || !b) continue
    const key = `${a.player_id}-${b.player_id}`
    const cur = seen.get(key) ?? { a, b, total: 0, ab: 0, ba: 0 }
    cur.total += e.n_passes
    if (e.passer_id === a.player_id) cur.ab += e.n_passes
    else cur.ba += e.n_passes
    seen.set(key, cur)
  }
  return [...seen.values()].sort((x, y) => x.total - y.total)
}

const PARTICLES = new Set(['de', 'di', 'van', 'von', 'el', 'al', 'la', 'da', 'dos', 'der', 'den'])

/** Display surname, keeping name particles ("De Paul", "Van Dijk"). */
export function lastName(full: string): string {
  const parts = full.split(' ')
  if (parts.length === 1) return full
  let start = parts.length - 1
  while (start > 0 && PARTICLES.has(parts[start - 1].toLowerCase())) start -= 1
  return parts.slice(start).join(' ')
}

/**
 * Label side per node: true = label above. When two nodes sit close together,
 * the upper node's label goes above so the labels separate.
 */
export function labelAbove(nodes: PassNode[]): Map<number, boolean> {
  const out = new Map<number, boolean>()
  for (const n of nodes) {
    let above = false
    for (const m of nodes) {
      if (m.player_id === n.player_id) continue
      const d = Math.hypot(m.avg_x - n.avg_x, m.avg_y - n.avg_y)
      if (d < 8 && n.avg_y <= m.avg_y) above = true
    }
    out.set(n.player_id, above)
  }
  return out
}
