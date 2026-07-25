import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

export function Watchlist({ teamId, teamName }: { teamId: number; teamName: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['watchlist', teamId],
    queryFn: () => api.watchlist(teamId),
  })

  if (isLoading || !data) return <div className="placeholder">Loading watchlist…</div>
  if (data.length === 0)
    return <div className="placeholder">No players with enough minutes (180+).</div>

  const maxXt = Math.max(...data.map((p) => p.xt_per_90))

  return (
    <div style={{ maxWidth: 760 }}>
      <p className="sub" style={{ color: 'var(--muted)', margin: '0 0 12px' }}>
        {teamName}'s most dangerous ball progressors — expected threat created per 90 minutes
        (completed passes and carries, positive ΔV). Minimum 180 minutes played.
      </p>
      {data.map((p, i) => (
        <div key={p.player_id} className="watch-card">
          <div className="watch-rank">{i + 1}</div>
          <div className="watch-body">
            <div className="watch-name">
              {p.jersey_number != null && <span className="watch-jersey">#{p.jersey_number}</span>}
              <b>{p.name}</b>
              <span className="watch-pos">{p.position ?? ''}</span>
            </div>
            <div className="watch-bar-row">
              <div className="pct-track" style={{ flex: 1 }}>
                <div
                  className="pct-fill threat"
                  style={{ width: `${(p.xt_per_90 / maxXt) * 100}%` }}
                />
              </div>
              <span className="watch-xt">{p.xt_per_90.toFixed(2)} xT/90</span>
            </div>
            {p.note && <div className="watch-note">{p.note}</div>}
            <div className="watch-meta">
              {Math.round(p.minutes)} mins · {p.n_actions.toLocaleString()} completed
              passes/carries · {p.xt_total.toFixed(1)} xT total
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
