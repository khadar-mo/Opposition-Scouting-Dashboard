import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, compKey, parseCompKey, type CompKey } from './api'
import { ThreatMap } from './views/ThreatMap'
import { PassNetwork } from './views/PassNetwork'
import { Patterns } from './views/Patterns'
import { SetPieces } from './views/SetPieces'
import { Watchlist } from './views/Watchlist'
import { Report } from './views/Report'
import { Ask } from './views/Ask'

const TABS = [
  'Threat map',
  'Pass network',
  'Build-up patterns',
  'Set pieces',
  'Watchlist',
  'Match report',
  'Ask',
] as const
type Tab = (typeof TABS)[number]

const DEFAULT_COMP: CompKey = '43-106' // FIFA World Cup 2022

function initials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function shortCompName(name: string, season: string): string {
  return `${name.replace('FIFA ', '').replace('UEFA ', '')} ${season}`
}

function initialState(): { team: number | null; tab: Tab; comp: CompKey } {
  const params = new URLSearchParams(window.location.search)
  const team = params.get('team')
  const tab = params.get('tab')
  const comp = parseCompKey(params.get('comp') ?? '')
  return {
    team: team ? Number(team) : null,
    tab: TABS.includes(tab as Tab) ? (tab as Tab) : 'Threat map',
    comp: comp ? compKey(comp) : DEFAULT_COMP,
  }
}

function syncUrl(team: number | null, tab: Tab, comp: CompKey) {
  const params = new URLSearchParams()
  if (comp !== DEFAULT_COMP) params.set('comp', comp)
  if (team !== null) params.set('team', String(team))
  if (tab !== 'Threat map') params.set('tab', tab)
  const q = params.toString()
  window.history.replaceState(null, '', q ? `?${q}` : window.location.pathname)
}

export default function App() {
  const [teamId, setTeamIdRaw] = useState<number | null>(() => initialState().team)
  const [tab, setTabRaw] = useState<Tab>(() => initialState().tab)
  const [comp, setCompRaw] = useState<CompKey>(() => initialState().comp)
  const [search, setSearch] = useState('')

  const competitionsQuery = useQuery({
    queryKey: ['competitions'],
    queryFn: api.competitions,
  })
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: api.health })
  const askEnabled = healthQuery.data?.ask_enabled ?? false
  const visibleTabs = askEnabled ? TABS : TABS.filter((t) => t !== 'Ask')
  const teamsQuery = useQuery({
    queryKey: ['teams', comp],
    queryFn: () => api.teams(comp),
  })
  const teams = useMemo(() => teamsQuery.data ?? [], [teamsQuery.data])
  const filtered = useMemo(
    () => teams.filter((t) => t.name.toLowerCase().includes(search.toLowerCase())),
    [teams, search],
  )
  const selected = teams.find((t) => t.team_id === teamId) ?? null

  const setTeamId = (id: number) => {
    setTeamIdRaw(id)
    syncUrl(id, tab, comp)
  }
  const setTab = (t: Tab) => {
    setTabRaw(t)
    syncUrl(teamId, t, comp)
  }
  const switchComp = async (next: CompKey) => {
    setCompRaw(next)
    // Keep the selected team when it exists in the other tournament
    // (Spain, France, England…); otherwise clear the selection.
    let keep: number | null = null
    if (teamId !== null) {
      const nextTeams = await api.teams(next)
      keep = nextTeams.some((t) => t.team_id === teamId) ? teamId : null
    }
    setTeamIdRaw(keep)
    syncUrl(keep, tab, next)
  }

  const profileQuery = useQuery({
    queryKey: ['profile', teamId, comp],
    queryFn: () => api.profile(teamId ?? 0, comp),
    enabled: teamId !== null && selected !== null,
  })
  const record = profileQuery.data?.record
  const competitions = competitionsQuery.data ?? []
  const activeComp = competitions.find((c) => compKey(c) === comp)

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>Opposition Scouting</h1>
          <span>StatsBomb open data</span>
        </div>
        <div className="comp-toggle" role="tablist" aria-label="Competition">
          {competitions.map((c) => (
            <button
              key={compKey(c)}
              role="tab"
              aria-selected={compKey(c) === comp}
              className={`comp-btn${compKey(c) === comp ? ' active' : ''}`}
              onClick={() => void switchComp(compKey(c))}
            >
              {shortCompName(c.name, c.season_name)}
            </button>
          ))}
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
            {activeComp && (
              <p style={{ fontSize: 12.5 }}>
                Showing {activeComp.name} {activeComp.season_name} ·{' '}
                {activeComp.n_matches} matches
              </p>
            )}
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
              {activeComp && (
                <span className="comp-chip">
                  {shortCompName(activeComp.name, activeComp.season_name)}
                </span>
              )}
            </header>
            <nav className="tabs">
              {visibleTabs.map((t) => (
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
                <ThreatMap teamId={selected.team_id} teamName={selected.name} comp={comp} />
              )}
              {tab === 'Pass network' && (
                <PassNetwork teamId={selected.team_id} teamName={selected.name} comp={comp} />
              )}
              {tab === 'Build-up patterns' && (
                <Patterns teamId={selected.team_id} teamName={selected.name} comp={comp} />
              )}
              {tab === 'Set pieces' && (
                <SetPieces teamId={selected.team_id} teamName={selected.name} comp={comp} />
              )}
              {tab === 'Watchlist' && (
                <Watchlist teamId={selected.team_id} teamName={selected.name} comp={comp} />
              )}
              {tab === 'Match report' && <Report teamId={selected.team_id} comp={comp} />}
              {tab === 'Ask' && askEnabled && (
                <Ask teamId={selected.team_id} teamName={selected.name} comp={comp} />
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
