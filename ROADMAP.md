# Roadmap & product decisions

This tool was built against a persona (a first-team analyst preparing on a
Tuesday for a Saturday fixture), not against a stakeholder — so the honest next
step isn't more features, it's validation. This page records what I'd put in
front of analysts first, what I deliberately didn't build, and the bets I'd
make next.

## Questions I'd validate with analysts before building more

1. **Is "threat by zone of origin" the right cut?** Analysts may care more
   about *destination* (where chances are finished from) or the *link* (origin →
   destination flows). The schema already stores both ends of every action, so
   flipping or connecting the aggregation is cheap — but which one changes a
   game plan is an analyst call, not an engineering one.
2. **Pattern granularity.** k=8 global clusters keep labels comparable across
   opponents. Would analysts rather have fewer, broader patterns (easier to
   brief) or per-opponent clustering (sharper, but "left half-space entry"
   would mean something different every week)?
3. **What does the coach actually read?** The one-page report is my guess at a
   two-minute artefact. The real test is handing it to a coach before a
   friendly and watching which sections they skip.
4. **Phase definitions.** The pass-network phases follow StatsBomb's
   play_pattern. Clubs usually have their own phase model (build-up /
   progression / final third / transitions defined on pitch thirds and time
   since regain). Adopting the club's definitions is a small derive-step change
   and a big trust win.
5. **Watchlist framing.** xT/90 rewards high-usage creators. Analysts may want
   role-relative rankings ("most dangerous full-back") or minutes-weighted
   confidence intervals before they'd quote it in a meeting.

## Deliberately not built (and why)

- **Live/in-match features** — the open data is post-match; pretending
  otherwise would demo something the data can't support.
- **Defensive profiles** (pressing triggers, block height) — a second product
  surface; better to make one surface excellent and validated first.
- **Player-level radar comparisons** — well-served by existing tools; the gap
  this project fills is *team* preparation.
- **Per-opponent model fine-tuning** — 3–7 matches per team is nowhere near
  enough; the honest unit of learning is the tournament, with per-team
  aggregation on top.
- **An LLM chat interface as the primary UX** — a chat box hides the sample
  sizes and provenance this tool works hard to surface. (A grounded,
  clearly-optional Q&A layer is a separate experiment — see below.)

## Next bets, in order

1. **Pressure-aware threat (research)** — the 360 freeze-frames support
   defender-context features (defenders between ball and goal, nearest-defender
   distance). Ablate against the position-only model; ship only what survives
   scrutiny. Status: **done** — see `ml/EVALUATION.md` and the threat map's 'Under pressure' toggle.
2. **Match-pack automation** — one command that renders the printable report
   for a full fixture list; the "Monday morning routine". Status: **done** — `python -m pipeline matchpack`.
3. **Opponent Q&A (experiment, off by default)** — natural-language questions
   answered strictly from the precomputed tables, with numbers cited, behind an
   environment flag so the core product never depends on an external API.
   Status: **done** — the "Ask" tab, visible only when `ANTHROPIC_API_KEY` is set.
4. **Club phase model + destination threat maps** — pending answers to
   questions 1 and 4 above.
