/** Typed client for the scouting API. */

export interface Competition {
  competition_id: number
  season_id: number
  name: string
  season_name: string
  n_matches: number
}

/** Compact key for a competition/season pair, e.g. "43-106". */
export type CompKey = `${number}-${number}`

export function compKey(c: { competition_id: number; season_id: number }): CompKey {
  return `${c.competition_id}-${c.season_id}`
}

export function parseCompKey(key: string): { competition_id: number; season_id: number } | null {
  const m = /^(\d+)-(\d+)$/.exec(key)
  return m ? { competition_id: Number(m[1]), season_id: Number(m[2]) } : null
}

export interface Team {
  team_id: number
  name: string
  n_matches: number
}

export interface MatchRow {
  match_id: number
  match_date: string
  stage: string
  home_score: number
  away_score: number
  home_team: string
  away_team: string
}

export interface Profile {
  team: { team_id: number; name: string }
  record: {
    played: number
    won: number
    drawn: number
    goals_for: number
    goals_against: number
  }
  threat: {
    total_xg: number
    shot_sequences: number
    sequences: number
    avg_sequence_duration: number
    avg_directness: number | null
  }
  matches: MatchRow[]
}

export interface ThreatZone {
  zone_x: number
  zone_y: number
  xt: number
  n_actions: number
}

export interface PassNode {
  player_id: number
  name: string
  jersey_number: number | null
  position: string | null
  avg_x: number
  avg_y: number
  n_touches: number
}

export interface PassEdge {
  passer_id: number
  receiver_id: number
  n_passes: number
}

export interface PassNetwork {
  phase: string
  nodes: PassNode[]
  edges: PassEdge[]
  total_passes: number
}

export interface SequenceStep {
  type: string
  x: number
  y: number
  end_x: number | null
  end_y: number | null
  minute: number
  second: number
  player: string | null
}

export interface Representative {
  sequence_id: number
  match_id: number
  xg: number | null
  ended_in_shot: boolean
  home_team: string
  away_team: string
  stage: string
  steps: SequenceStep[]
}

export interface Pattern {
  cluster_id: number
  label: string
  description: string
  n_sequences: number
  pct: number
  representatives: Representative[]
}

export interface Corner {
  side: 'left' | 'right'
  delivery_x: number | null
  delivery_y: number | null
  delivery_zone: string
  swing: string | null
  first_contact_x: number | null
  first_contact_y: number | null
  led_to_shot: boolean
  won_first_contact: boolean | null
  first_contact_player: string | null
}

export interface SetPieces {
  corners: Corner[]
  zones: { delivery_zone: string; n: number; shots: number }[]
  n_corners: number
}

export interface WatchlistPlayer {
  player_id: number
  name: string
  position: string | null
  jersey_number: number | null
  minutes: number
  n_actions: number
  xt_total: number
  xt_per_90: number
  note: string | null
}

export interface Report {
  profile: Profile
  top_zones: ThreatZone[]
  patterns: { label: string; description: string; n_sequences: number; pct: number }[]
  set_pieces: { delivery_zone: string; n: number; shots: number }[]
  watchlist: WatchlistPlayer[]
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`)
  return res.json() as Promise<T>
}

function qs(comp: CompKey, extra: Record<string, string> = {}): string {
  const parsed = parseCompKey(comp)
  const params = new URLSearchParams(extra)
  if (parsed) {
    params.set('competition_id', String(parsed.competition_id))
    params.set('season_id', String(parsed.season_id))
  }
  return `?${params.toString()}`
}

export const api = {
  competitions: () => get<Competition[]>('/api/competitions'),
  teams: (comp: CompKey) => get<Team[]>(`/api/teams${qs(comp)}`),
  profile: (id: number, comp: CompKey) =>
    get<Profile>(`/api/teams/${id}/profile${qs(comp)}`),
  threatMap: (id: number, comp: CompKey) =>
    get<ThreatZone[]>(`/api/teams/${id}/threat-map${qs(comp)}`),
  passNetwork: (id: number, comp: CompKey, phase: string) =>
    get<PassNetwork>(`/api/teams/${id}/pass-network${qs(comp, { phase })}`),
  patterns: (id: number, comp: CompKey) =>
    get<Pattern[]>(`/api/teams/${id}/patterns${qs(comp)}`),
  setPieces: (id: number, comp: CompKey) =>
    get<SetPieces>(`/api/teams/${id}/set-pieces${qs(comp)}`),
  watchlist: (id: number, comp: CompKey) =>
    get<WatchlistPlayer[]>(`/api/teams/${id}/watchlist${qs(comp)}`),
  report: (id: number, comp: CompKey) =>
    get<Report>(`/api/teams/${id}/report${qs(comp)}`),
}
