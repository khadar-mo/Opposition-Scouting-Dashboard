import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type CompKey } from '../api'
import { Pitch } from '../components/Pitch'
import { TooltipLayer } from '../components/Tooltip'
import { useTooltip } from '../lib/useTooltip'
import { combineEdges, labelAbove, lastName } from '../lib/network'

const PHASES = [
  { key: 'all', label: 'All phases' },
  { key: 'open_play', label: 'Open play' },
  { key: 'goal_kick', label: 'From goal kick' },
  { key: 'counter', label: 'Counter' },
  { key: 'set_piece', label: 'Set piece' },
] as const

export function PassNetwork({ teamId, teamName, comp }: { teamId: number; teamName: string; comp: CompKey }) {
  const [phase, setPhase] = useState<string>('all')
  const { data, isLoading } = useQuery({
    queryKey: ['passnet', teamId, comp, phase],
    queryFn: () => api.passNetwork(teamId, comp, phase),
  })
  const { tip, show, hide } = useTooltip()

  const combined = data ? combineEdges(data.nodes, data.edges) : []
  const maxEdge = Math.max(1, ...combined.map((e) => e.total))
  const maxTouches = data ? Math.max(1, ...data.nodes.map((n) => n.n_touches)) : 1
  const above = data ? labelAbove(data.nodes) : new Map<number, boolean>()

  return (
    <div style={{ maxWidth: 860 }}>
      <div className="panel">
        <h3>How {teamName} connect</h3>
        <p className="sub">
          The 11 most involved players in this phase — average on-ball position, line thickness =
          completed passes between the pair.{' '}
          {data ? `${data.total_passes.toLocaleString()} completed passes in phase.` : ''}
        </p>
        <div className="seg-row" role="tablist" aria-label="Match phase">
          {PHASES.map((p) => (
            <button
              key={p.key}
              role="tab"
              aria-selected={phase === p.key}
              className={`seg${phase === p.key ? ' active' : ''}`}
              onClick={() => setPhase(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>
        {isLoading || !data ? (
          <div className="placeholder">Loading network…</div>
        ) : (
          <Pitch>
            {combined.map((e) => (
              <line
                key={`${e.a.player_id}-${e.b.player_id}`}
                x1={e.a.avg_x}
                y1={e.a.avg_y}
                x2={e.b.avg_x}
                y2={e.b.avg_y}
                stroke="var(--accent)"
                strokeWidth={0.25 + (e.total / maxEdge) * 1.9}
                strokeOpacity={0.28 + (e.total / maxEdge) * 0.6}
                strokeLinecap="round"
                onMouseMove={(ev) =>
                  show(ev, (
                    <>
                      <b>
                        {lastName(e.a.name)} ↔ {lastName(e.b.name)}
                      </b>
                      <div>{e.total} passes</div>
                      <div style={{ color: 'var(--muted)' }}>
                        {lastName(e.a.name)} → {lastName(e.b.name)}: {e.ab} ·{' '}
                        {lastName(e.b.name)} → {lastName(e.a.name)}: {e.ba}
                      </div>
                    </>
                  ))
                }
                onMouseLeave={hide}
              />
            ))}
            {data.nodes.map((n) => {
              const r = 2.1 + Math.sqrt(n.n_touches / maxTouches) * 1.6
              return (
                <g key={n.player_id}>
                  <circle
                    cx={n.avg_x}
                    cy={n.avg_y}
                    r={r}
                    fill="var(--surface-2)"
                    stroke="var(--accent)"
                    strokeWidth={0.45}
                    onMouseMove={(ev) =>
                      show(ev, (
                        <>
                          <b>
                            {n.jersey_number != null ? `#${n.jersey_number} ` : ''}
                            {n.name}
                          </b>
                          <div>{n.position ?? 'Unknown position'}</div>
                          <div style={{ color: 'var(--muted)' }}>
                            {n.n_touches.toLocaleString()} pass involvements
                          </div>
                        </>
                      ))
                    }
                    onMouseLeave={hide}
                  />
                  <text
                    x={n.avg_x}
                    y={n.avg_y + 0.9}
                    textAnchor="middle"
                    fontSize={2.4}
                    fontWeight={600}
                    fill="var(--ink)"
                    pointerEvents="none"
                  >
                    {n.jersey_number ?? ''}
                  </text>
                  <text
                    x={n.avg_x}
                    y={above.get(n.player_id) ? n.avg_y - r - 1.1 : n.avg_y + r + 2.6}
                    textAnchor="middle"
                    fontSize={2.2}
                    fill="var(--ink-2)"
                    pointerEvents="none"
                    style={{ paintOrder: 'stroke', stroke: 'var(--pitch)', strokeWidth: 0.5 }}
                  >
                    {lastName(n.name)}
                  </text>
                </g>
              )
            })}
          </Pitch>
        )}
        <div className="legend-row">
          <svg width="52" height="10">
            <line x1="2" y1="5" x2="20" y2="5" stroke="var(--accent)" strokeWidth="1" strokeOpacity="0.4" />
            <line x1="30" y1="5" x2="50" y2="5" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" />
          </svg>
          <span>few ↔ many passes · circle size = involvement · hover for exact counts</span>
        </div>
      </div>
      <TooltipLayer tip={tip} />
    </div>
  )
}
