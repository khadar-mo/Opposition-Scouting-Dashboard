import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import { ThreatMap } from './views/ThreatMap'
import { PassNetwork } from './views/PassNetwork'
import { Patterns } from './views/Patterns'
import { SetPieces } from './views/SetPieces'
import { Watchlist } from './views/Watchlist'
import { Report } from './views/Report'

const TABS = [
  'Threat map',
  'Pass network',
  'Build-up patterns',
  'Set pieces',
  'Watchlist',
  'Match report',
] as const
type Tab = (typeof TABS)[number]

function initials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function initialState(): { team: number | null; tab: Tab } {
  const params = new URLSearchParams(window.location.search)
  const team = params.get('team')
  const tab = params.get('tab')
  return {
    team: team ? Number(team) : null,
    tab: TABS.includes(tab as Tab) ? (tab as Tab) : 'Threat map',
  }
}

function syncUrl(team: number | null, tab: Tab) {
  const params = new URLSearchParams()
  if (team !== null) params.set('team', String(team))
  if (tab !== 'Threat map') params.set('tab', tab)
  const qs = params.toString()
  window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname)
}

export default function App() {
  const [teamId, setTeamIdRaw] = useState<number | null>(() => initialState().team)
  const [tab, setTabRaw] = useState<Tab>(() => initialState().tab)
  const [search, setSearch] = useState('')
  const setTeamId = (id: number) => {
    setTeamIdRaw(id)
    syncUrl(id, tab)
  }
  const setTab = (t: Tab) => {
    setTabRaw(t)
    syncUrl(teamId, t)
  }

  const teamsQuery = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const teams = useMemo(() => teamsQuery.data ?? [], [teamsQuery.data])
  const filtered = useMemo(
    () => teams.filter((t) => t.name.toLowerCase().includes(search.toLowerCase())),
    [teams, search],
  )
  const selected = teams.find((t) => t.team_id === teamId) ?? null

  const profileQuery = useQuery({
    queryKey: ['profile', teamId],
    queryFn: () => api.profile(teamId ?? 0),
    enabled: teamId !== null,
  })
  const record = profileQuery.data?.record

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>Opposition Scouting</h1>
          <span>FIFA World Cup 2022 · StatsBomb open data</span>
        </div>
        <input
          className="team-search"
          placeholder="Find opponent…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search teams"
        />
        <nav className="team-list">
          {teamsQuery.isLoading && <div className="placeholder">Loading…</div>}
          {filtered.map((t) => (
            <button
              key={t.team_id}
              className={`team-item${t.team_id === teamId ? ' active' : ''}`}
              onClick={() => setTeamId(t.team_id)}
            >
              <span className="team-badge">{initials(t.name)}</span>
              {t.name}
              <span className="team-matches">{t.n_matches}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        {selected === null ? (
          <div className="placeholder" style={{ margin: 'auto', maxWidth: 420 }}>
            <h2 style={{ color: 'var(--ink)' }}>Pick an opponent</h2>
            <p>
              Select a team to get their tactical profile: where they generate threat, how they
              build up, who to watch, and their set-piece habits.
            </p>
          </div>
        ) : (
          <>
            <header className="topbar">
              <h2>{selected.name}</h2>
              {record && (
                <span className="record">
                  <b>
                    {record.won}W {record.drawn}D {record.played - record.won - record.drawn}L
                  </b>
                  {' · '}
                  {record.goals_for} scored, {record.goals_against} conceded ·{' '}
                  {selected.n_matches} matches
                </span>
              )}
            </header>
            <nav className="tabs">
              {TABS.map((t) => (
                <button
                  key={t}
                  className={`tab${t === tab ? ' active' : ''}`}
                  onClick={() => setTab(t)}
                >
                  {t}
                </button>
              ))}
            </nav>
            <section className="view">
              {tab === 'Threat map' && (
                <ThreatMap teamId={selected.team_id} teamName={selected.name} />
              )}
              {tab === 'Pass network' && (
                <PassNetwork teamId={selected.team_id} teamName={selected.name} />
              )}
              {tab === 'Build-up patterns' && (
                <Patterns teamId={selected.team_id} teamName={selected.name} />
              )}
              {tab === 'Set pieces' && (
                <SetPieces teamId={selected.team_id} teamName={selected.name} />
              )}
              {tab === 'Watchlist' && (
                <Watchlist teamId={selected.team_id} teamName={selected.name} />
              )}
              {tab === 'Match report' && <Report teamId={selected.team_id} />}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
