import { describe, expect, it } from 'vitest'
import { combineEdges, labelAbove, lastName } from './network'
import type { PassNode } from '../api'

const node = (id: number, x = 50, y = 40): PassNode => ({
  player_id: id,
  name: `Player ${id}`,
  jersey_number: id,
  position: null,
  avg_x: x,
  avg_y: y,
  n_touches: 10,
})

describe('lastName', () => {
  it('takes the final word by default', () => {
    expect(lastName('Lionel Messi')).toBe('Messi')
    expect(lastName('Kylian Mbappé Lottin')).toBe('Lottin')
  })
  it('keeps name particles attached', () => {
    expect(lastName('Rodrigo De Paul')).toBe('De Paul')
    expect(lastName('Virgil van Dijk')).toBe('van Dijk')
    expect(lastName('Achraf El Kaabi')).toBe('El Kaabi')
  })
  it('handles single-word names', () => {
    expect(lastName('Raphinha')).toBe('Raphinha')
  })
})

describe('combineEdges', () => {
  it('merges both directions into one edge with per-direction counts', () => {
    const nodes = [node(1), node(2)]
    const edges = [
      { passer_id: 1, receiver_id: 2, n_passes: 7 },
      { passer_id: 2, receiver_id: 1, n_passes: 5 },
    ]
    const combined = combineEdges(nodes, edges)
    expect(combined).toHaveLength(1)
    expect(combined[0].total).toBe(12)
    expect(combined[0].ab).toBe(7)
    expect(combined[0].ba).toBe(5)
  })
  it('drops edges whose endpoints are not displayed', () => {
    const combined = combineEdges([node(1)], [{ passer_id: 1, receiver_id: 99, n_passes: 3 }])
    expect(combined).toHaveLength(0)
  })
})

describe('labelAbove', () => {
  it('flips the upper label of a close pair above the node', () => {
    const nodes = [node(1, 50, 40), node(2, 50, 44)]
    const sides = labelAbove(nodes)
    expect(sides.get(1)).toBe(true)
    expect(sides.get(2)).toBe(false)
  })
  it('leaves isolated nodes labelled below', () => {
    const sides = labelAbove([node(1, 20, 20), node(2, 80, 60)])
    expect(sides.get(1)).toBe(false)
    expect(sides.get(2)).toBe(false)
  })
})
