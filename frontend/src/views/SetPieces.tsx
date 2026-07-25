import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Pitch } from '../components/Pitch'
import { TooltipLayer } from '../components/Tooltip'
import { useTooltip } from '../lib/useTooltip'

const ZONE_LABELS: Record<string, string> = {
  near_post: 'Near post',
  central: 'Central',
  far_post: 'Far post',
  short: 'Short',
  edge_of_box: 'Edge of box',
  out_of_box: 'Out of box',
}

const SWING_COLOR: Record<string, string> = {
  Inswinging: 'var(--accent)',
  Outswinging: 'var(--threat-4)',
  Straight: 'var(--muted)',
}

export function SetPieces({ teamId, teamName }: { teamId: number; teamName: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['setpieces', teamId],
    queryFn: () => api.setPieces(teamId),
  })
  const { tip, show, hide } = useTooltip()

  if (isLoading || !data) return <div className="placeholder">Loading set pieces…</div>
  if (data.n_corners === 0)
    return <div className="placeholder">No corners recorded for this team.</div>

  const contacts = data.corners.filter((c) => c.first_contact_x != null)
  const wonContacts = contacts.filter((c) => c.won_first_contact)
  const shots = data.corners.filter((c) => c.led_to_shot)
  const leftCorners = data.corners.filter((c) => c.side === 'left')

  return (
    <div style={{ maxWidth: 1040 }}>
      <div className="stat-row">
        <div className="stat-tile">
          <div className="label">Corners taken</div>
          <div className="value">{data.n_corners}</div>
          <div className="hint">
            {leftCorners.length} left · {data.n_corners - leftCorners.length} right
          </div>
        </div>
        <div className="stat-tile">
          <div className="label">First contact won</div>
          <div className="value">
            {contacts.length ? `${Math.round((wonContacts.length / contacts.length) * 100)}%` : '—'}
          </div>
          <div className="hint">{wonContacts.length} of {contacts.length} with known contact</div>
        </div>
        <div className="stat-tile">
          <div className="label">Led to a shot</div>
          <div className="value">{Math.round((shots.length / data.n_corners) * 100)}%</div>
          <div className="hint">{shots.length} corners → shot in the same possession</div>
        </div>
        <div className="stat-tile">
          <div className="label">Favourite delivery</div>
          <div className="value" style={{ fontSize: 17 }}>
            {ZONE_LABELS[data.zones[0]?.delivery_zone] ?? '—'}
          </div>
          <div className="hint">
            {data.zones[0] ? `${data.zones[0].n} of ${data.n_corners} deliveries` : ''}
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>Corner deliveries</h3>
          <p className="sub">
            Where {teamName}'s corners land. Colour = swing; red ring = led to a shot.
          </p>
          <Pitch half showDirection={false}>
            {data.corners.map(
              (c, i) =>
                c.delivery_x != null &&
                c.delivery_y != null && (
                  <g key={i}>
                    {c.led_to_shot && (
                      <circle
                        cx={c.delivery_x}
                        cy={c.delivery_y}
                        r={1.9}
                        fill="none"
                        stroke="var(--shot)"
                        strokeWidth={0.35}
                      />
                    )}
                    <circle
                      cx={c.delivery_x}
                      cy={c.delivery_y}
                      r={1.1}
                      fill={SWING_COLOR[c.swing ?? 'Straight'] ?? 'var(--muted)'}
                      fillOpacity={0.9}
                      stroke="var(--pitch)"
                      strokeWidth={0.2}
                      onMouseMove={(e) =>
                        show(e, (
                          <>
                            <b>
                              {c.side === 'left' ? 'Left' : 'Right'}-side corner ·{' '}
                              {c.swing ?? 'unknown swing'}
                            </b>
                            <div>{ZONE_LABELS[c.delivery_zone]} delivery</div>
                            {c.led_to_shot && <div style={{ color: 'var(--shot)' }}>led to a shot</div>}
                          </>
                        ))
                      }
                      onMouseLeave={hide}
                    />
                  </g>
                ),
            )}
          </Pitch>
          <div className="legend-row">
            <span className="dot" style={{ background: 'var(--accent)' }} /> inswing
            <span className="dot" style={{ background: 'var(--threat-4)' }} /> outswing
            <span className="dot" style={{ background: 'var(--muted)' }} /> straight/short
            <span className="dot" style={{ border: '1.5px solid var(--shot)', background: 'transparent' }} />{' '}
            led to shot
          </div>
        </div>

        <div className="panel">
          <h3>First contacts</h3>
          <p className="sub">
            Who met the delivery first (from the event chain; ● won by {teamName}, ○ lost).
          </p>
          <Pitch half showDirection={false}>
            {contacts.map((c, i) => (
              <circle
                key={i}
                cx={c.first_contact_x ?? 0}
                cy={c.first_contact_y ?? 0}
                r={1.1}
                fill={c.won_first_contact ? 'var(--accent)' : 'transparent'}
                stroke={c.won_first_contact ? 'var(--accent)' : 'var(--muted)'}
                strokeWidth={0.4}
                onMouseMove={(e) =>
                  show(e, (
                    <>
                      <b>{c.won_first_contact ? 'Won' : 'Lost'} first contact</b>
                      {c.first_contact_player && <div>{c.first_contact_player}</div>}
                      <div style={{ color: 'var(--muted)' }}>
                        {c.side === 'left' ? 'left' : 'right'}-side corner
                      </div>
                    </>
                  ))
                }
                onMouseLeave={hide}
              />
            ))}
          </Pitch>
          <div className="zone-bars">
            {data.zones
              .filter((z) => z.delivery_zone !== 'out_of_box')
              .map((z) => (
                <div key={z.delivery_zone} className="zone-bar-row">
                  <span className="zone-name">{ZONE_LABELS[z.delivery_zone]}</span>
                  <div className="pct-track" style={{ flex: 1 }}>
                    <div
                      className="pct-fill"
                      style={{ width: `${(z.n / data.n_corners) * 100}%` }}
                    />
                  </div>
                  <span className="zone-count">
                    {z.n}
                    {z.shots > 0 ? ` (${z.shots} shot${z.shots > 1 ? 's' : ''})` : ''}
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>
      <p className="note">
        Sample: {data.n_corners} corners across {teamName}'s tournament. First-contact positions
        come from the event chain within 10s of the delivery; 360 freeze-frames back the
        delivery/contact locations.
      </p>
      <TooltipLayer tip={tip} />
    </div>
  )
}
