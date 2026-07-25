import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { scaleSequential } from 'd3-scale'
import { piecewise, interpolateRgb } from 'd3-interpolate'
import { api, type CompKey, type ThreatZone } from '../api'
import { Pitch } from '../components/Pitch'
import { TooltipLayer } from '../components/Tooltip'
import { useTooltip } from '../lib/useTooltip'

const RAMP = ['#1c1917', '#3a2313', '#6b3a10', '#a5570e', '#d97b1e', '#ffa245', '#ffc98a']

type Mode = 'all' | 'pressured'

const zoneValue = (z: ThreatZone, mode: Mode) => (mode === 'all' ? z.xt : z.xt_pressured)

export function ThreatMap({ teamId, teamName, comp }: { teamId: number; teamName: string; comp: CompKey }) {
  const { data, isLoading } = useQuery({
    queryKey: ['threat', teamId, comp],
    queryFn: () => api.threatMap(teamId, comp),
  })
  const { tip, show, hide } = useTooltip()
  const [mode, setMode] = useState<Mode>('all')

  if (isLoading) return <div className="placeholder">Loading threat map…</div>
  if (!data || data.length === 0)
    return <div className="placeholder">No threat data for this team.</div>

  const maxXt = Math.max(...data.map((z) => zoneValue(z, mode)))
  const totalXt = data.reduce((s, z) => s + zoneValue(z, mode), 0)
  const totalActions = data.reduce(
    (s, z) => s + (mode === 'all' ? z.n_actions : z.n_pressured),
    0,
  )
  const interp = piecewise(interpolateRgb, RAMP)
  // Mild power lift (t^0.75): pure linear leaves the middle third unreadably
  // dark, √ makes everything look hot; 0.75 keeps only real hotspots bright.
  const color = scaleSequential((t: number) => interp(Math.pow(t, 0.75))).domain([0, maxXt])

  const top = [...data].sort((a, b) => zoneValue(b, mode) - zoneValue(a, mode)).slice(0, 3)
  const laneNames = ['left wing', 'left half-space', 'central', 'right half-space', 'right wing']

  return (
    <div style={{ maxWidth: 860 }}>
      <div className="panel">
        <h3>Where {teamName} generate threat</h3>
        <p className="sub">
          Expected-threat (xT) created by completed passes and carries, by zone of origin —
          summed positive ΔV from the possession-value model. {totalActions.toLocaleString()}{' '}
          {mode === 'pressured' ? 'pressured ' : ''}actions across the tournament. Attack →
        </p>
        <div className="seg-row" role="tablist" aria-label="Pressure filter">
          <button
            role="tab"
            aria-selected={mode === 'all'}
            className={`seg${mode === 'all' ? ' active' : ''}`}
            onClick={() => setMode('all')}
          >
            All origins
          </button>
          <button
            role="tab"
            aria-selected={mode === 'pressured'}
            className={`seg${mode === 'pressured' ? ' active' : ''}`}
            onClick={() => setMode('pressured')}
          >
            Under pressure
          </button>
        </div>
        <Pitch>
          {data.map((z) => (
            <rect
              key={`${z.zone_x}-${z.zone_y}`}
              x={z.zone_x * 10 + 0.15}
              y={z.zone_y * 10 + 0.15}
              width={9.7}
              height={9.7}
              rx={0.6}
              fill={color(zoneValue(z, mode))}
              opacity={0.88}
              onMouseMove={(e) =>
                show(e, (
                  <>
                    <b>{((zoneValue(z, mode) / totalXt) * 100).toFixed(1)}% of team threat</b>
                    <div>
                      {mode === 'all'
                        ? `${z.xt.toFixed(2)} xT from ${z.n_actions} actions`
                        : `${z.xt_pressured.toFixed(2)} xT from ${z.n_pressured} pressured actions`}
                    </div>
                    {mode === 'all' && z.xt > 0 && (
                      <div>
                        {((z.xt_pressured / z.xt) * 100).toFixed(0)}% of it created under pressure
                      </div>
                    )}
                    <div style={{ color: 'var(--muted)' }}>
                      {z.zone_x < 4 ? 'defensive third' : z.zone_x < 8 ? 'middle third' : 'final third'}
                      {' · '}
                      {laneNames[Math.min(4, Math.floor((z.zone_y * 10) / 16))]}
                    </div>
                  </>
                ))
              }
              onMouseLeave={hide}
            />
          ))}
        </Pitch>
        <div className="legend-row">
          <span>low</span>
          <div
            style={{
              width: 140,
              height: 8,
              borderRadius: 4,
              background: `linear-gradient(to right, ${RAMP.join(',')})`,
            }}
          />
          <span>high threat origin</span>
          <span style={{ marginLeft: 'auto' }}>hover any zone for xT and sample size</span>
        </div>
      </div>
      <p className="note">
        Top origins:{' '}
        {top
          .map(
            (z) =>
              `${z.zone_x < 8 ? (z.zone_x < 4 ? 'own third' : 'middle third') : 'final third'} / ${
                laneNames[Math.min(4, Math.floor((z.zone_y * 10) / 16))]
              } (${((zoneValue(z, mode) / totalXt) * 100).toFixed(0)}%)`,
          )
          .join(' · ')}
      </p>
      <TooltipLayer tip={tip} />
    </div>
  )
}
