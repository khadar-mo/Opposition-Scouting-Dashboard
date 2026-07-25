import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type CompKey, type Pattern, type Representative } from '../api'
import { Pitch } from '../components/Pitch'

function StepMarks({ rep, upto }: { rep: Representative; upto: number }) {
  const steps = rep.steps.slice(0, upto + 1)
  return (
    <>
      {steps.map((s, i) => {
        const isCurrent = i === upto
        const opacity = isCurrent ? 1 : 0.4 + (i / steps.length) * 0.3
        if (s.end_x == null || s.end_y == null) {
          return (
            <circle
              key={i}
              cx={s.x}
              cy={s.y}
              r={0.9}
              fill="var(--accent)"
              opacity={opacity}
            />
          )
        }
        const color =
          s.type === 'Shot' ? 'var(--shot)' : s.type === 'Carry' ? 'var(--accent-2)' : 'var(--accent)'
        return (
          <g key={i} opacity={opacity}>
            <line
              x1={s.x}
              y1={s.y}
              x2={s.end_x}
              y2={s.end_y}
              stroke={color}
              strokeWidth={isCurrent ? 0.7 : 0.45}
              strokeDasharray={s.type === 'Carry' ? '1.2 0.9' : undefined}
              strokeLinecap="round"
            />
            <circle cx={s.end_x} cy={s.end_y} r={isCurrent ? 1.1 : 0.7} fill={color} />
          </g>
        )
      })}
    </>
  )
}

function SequencePlayer({ rep }: { rep: Representative }) {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(true)
  const n = rep.steps.length

  useEffect(() => {
    setStep(0)
    setPlaying(true)
  }, [rep.sequence_id])

  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => {
      setStep((s) => {
        if (s >= n - 1) {
          setPlaying(false)
          return s
        }
        return s + 1
      })
    }, 700)
    return () => clearInterval(t)
  }, [playing, n])

  const current = rep.steps[Math.min(step, n - 1)]
  return (
    <div>
      <Pitch>
        <StepMarks rep={rep} upto={step} />
      </Pitch>
      <div className="player-controls">
        <button className="ctrl" onClick={() => setStep((s) => Math.max(0, s - 1))} aria-label="Previous step">
          ‹
        </button>
        <button className="ctrl" onClick={() => setPlaying((p) => !p)} aria-label="Play or pause">
          {playing ? '❚❚' : '▶'}
        </button>
        <button className="ctrl" onClick={() => setStep((s) => Math.min(n - 1, s + 1))} aria-label="Next step">
          ›
        </button>
        <span className="step-label">
          {step + 1}/{n} · {current.type}
          {current.player ? ` — ${current.player}` : ''} · {current.minute}′
        </span>
      </div>
      <div className="legend-row" style={{ marginTop: 6 }}>
        <svg width="120" height="10">
          <line x1="2" y1="5" x2="24" y2="5" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
          <line x1="46" y1="5" x2="68" y2="5" stroke="var(--accent-2)" strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" />
          <line x1="92" y1="5" x2="114" y2="5" stroke="var(--shot)" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span>pass · carry · shot</span>
      </div>
    </div>
  )
}

export function Patterns({ teamId, teamName, comp }: { teamId: number; teamName: string; comp: CompKey }) {
  const { data, isLoading } = useQuery({
    queryKey: ['patterns', teamId, comp],
    queryFn: () => api.patterns(teamId, comp),
  })
  const [selected, setSelected] = useState<number | null>(null)
  const [repIdx, setRepIdx] = useState(0)

  const patterns = useMemo(
    () => (data ?? []).filter((p) => p.representatives.length > 0).slice(0, 5),
    [data],
  )
  const active: Pattern | undefined =
    patterns.find((p) => p.cluster_id === selected) ?? patterns[0]
  const rep = active?.representatives[Math.min(repIdx, (active?.representatives.length ?? 1) - 1)]

  if (isLoading) return <div className="placeholder">Loading patterns…</div>
  if (patterns.length === 0)
    return <div className="placeholder">Not enough qualifying sequences for this team.</div>

  const maxPct = Math.max(...patterns.map((p) => p.pct))

  return (
    <div className="patterns-grid">
      <div>
        <p className="sub" style={{ margin: '0 0 10px', color: 'var(--muted)' }}>
          Recurring routes to the final third, clustered across all {teamName} possessions
          (open play; ≥4 on-ball actions). Share of the team's {' '}
          {patterns.reduce((s, p) => s + p.n_sequences, 0)} qualifying sequences.
        </p>
        {patterns.map((p) => (
          <button
            key={p.cluster_id}
            className={`pattern-card${p.cluster_id === active?.cluster_id ? ' active' : ''}`}
            onClick={() => {
              setSelected(p.cluster_id)
              setRepIdx(0)
            }}
          >
            <div className="pattern-head">
              <b>{(p.pct * 100).toFixed(0)}%</b>
              <span>{p.label}</span>
            </div>
            <div className="pct-track">
              <div className="pct-fill" style={{ width: `${(p.pct / maxPct) * 100}%` }} />
            </div>
            <div className="pattern-desc">{p.description}</div>
            <div className="pattern-n">{p.n_sequences} sequences</div>
          </button>
        ))}
      </div>
      <div className="panel" style={{ alignSelf: 'start' }}>
        <h3>{active?.label}</h3>
        <p className="sub">
          Representative sequence {repIdx + 1} of {active?.representatives.length} ·{' '}
          {rep ? `${rep.home_team} v ${rep.away_team} (${rep.stage})` : ''}
          {rep?.ended_in_shot ? ` · ended in a shot${rep.xg ? ` (xG ${rep.xg.toFixed(2)})` : ''}` : ''}
        </p>
        <div className="rep-row">
          {active?.representatives.map((r, i) => (
            <button
              key={r.sequence_id}
              className={`seg${i === repIdx ? ' active' : ''}`}
              onClick={() => setRepIdx(i)}
            >
              Example {i + 1}
            </button>
          ))}
        </div>
        {rep && <SequencePlayer rep={rep} />}
      </div>
    </div>
  )
}
