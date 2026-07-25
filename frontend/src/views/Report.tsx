import { useQuery } from '@tanstack/react-query'
import { api, type Report as ReportData } from '../api'

const LANES = ['left wing', 'left half-space', 'central areas', 'right half-space', 'right wing']
const ZONE_LABELS: Record<string, string> = {
  near_post: 'near post',
  central: 'central',
  far_post: 'far post',
  short: 'short',
  edge_of_box: 'edge of the box',
  out_of_box: 'out of the box',
}

function zoneName(zx: number, zy: number): string {
  const third = zx < 4 ? 'their own third' : zx < 8 ? 'the middle third' : 'the final third'
  return `${third}, ${LANES[Math.min(4, Math.floor((zy * 10) / 16))]}`
}

function keyThreatsParagraph(r: ReportData): string {
  const total = r.top_zones.reduce((s, z) => s + z.xt, 0)
  const zones = r.top_zones
    .map((z) => zoneName(z.zone_x, z.zone_y))
    .filter((v, i, a) => a.indexOf(v) === i)
  const t = r.profile.threat
  const directness =
    t.avg_directness == null
      ? ''
      : t.avg_directness > 0.42
        ? ' They progress the ball directly — expect quick, vertical attacks.'
        : t.avg_directness < 0.3
          ? ' They build patiently — deny central passing lanes and force them wide.'
          : ''
  void total
  return (
    `Danger originates mainly from ${zones.slice(0, 2).join(' and ')}. ` +
    `${t.shot_sequences} of ${t.sequences} possessions ended in a shot ` +
    `(total ${t.total_xg.toFixed(1)} xG).${directness}`
  )
}

export function Report({ teamId }: { teamId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['report', teamId],
    queryFn: () => api.report(teamId),
  })

  if (isLoading || !data) return <div className="placeholder">Building report…</div>

  const r = data
  const name = r.profile.team.name
  const rec = r.profile.record
  const corners = r.set_pieces.reduce((s, z) => s + z.n, 0)
  const cornerShots = r.set_pieces.reduce((s, z) => s + z.shots, 0)
  const topZone = r.set_pieces[0]

  return (
    <div className="report-wrap">
      <div className="report-actions no-print">
        <button className="print-btn" onClick={() => window.print()}>
          Print / save as PDF
        </button>
        <span style={{ color: 'var(--muted)', fontSize: 12 }}>
          One page, plain language — written for a two-minute pre-meeting read.
        </span>
      </div>

      <article className="report-page">
        <header className="report-header">
          <div>
            <h1>Opposition report — {name}</h1>
            <p className="report-sub">
              FIFA World Cup 2022 · {rec.played} matches ({rec.won}W {rec.drawn}D{' '}
              {rec.played - rec.won - rec.drawn}L, {rec.goals_for}–{rec.goals_against}) · StatsBomb
              event data
            </p>
          </div>
        </header>

        <section>
          <h2>Key threats</h2>
          <p>{keyThreatsParagraph(r)}</p>
          <ul>
            {r.watchlist.map((p) => (
              <li key={p.player_id}>
                <b>
                  {p.jersey_number != null ? `#${p.jersey_number} ` : ''}
                  {p.name}
                </b>{' '}
                — {p.note ?? `${p.xt_per_90.toFixed(2)} xT per 90 (${Math.round(p.minutes)} mins).`}
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2>How they attack</h2>
          <ul>
            {r.patterns.map((p) => (
              <li key={p.label}>
                <b>{(p.pct * 100).toFixed(0)}%</b> — {p.description}{' '}
                <span className="report-n">({p.n_sequences} sequences)</span>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2>Set-piece warnings</h2>
          <p>
            {corners} corners this tournament, {cornerShots} leading to a shot.
            {topZone &&
              ` Primary target: ${ZONE_LABELS[topZone.delivery_zone]} (${topZone.n} deliveries).`}{' '}
            {r.set_pieces
              .slice(1, 3)
              .map((z) => `${ZONE_LABELS[z.delivery_zone]}: ${z.n}`)
              .join(' · ')}
          </p>
        </section>

        <footer className="report-footer">
          Generated from StatsBomb open event data · xT = expected threat from a possession-value
          model trained on this tournament · sample sizes shown throughout — treat 3-match teams
          with caution.
        </footer>
      </article>
    </div>
  )
}
