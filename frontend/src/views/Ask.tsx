import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, type CompKey } from '../api'
import { paragraphs, renderEmphasis } from '../lib/text'

const SUGGESTIONS = [
  'Where do they create most of their danger, and does it survive pressure?',
  'How should we defend their corners?',
  'Which player should our full-backs worry about?',
]

export function Ask({ teamId, teamName, comp }: { teamId: number; teamName: string; comp: CompKey }) {
  const [question, setQuestion] = useState('')
  const mutation = useMutation({
    mutationFn: (q: string) => api.ask(teamId, comp, q),
  })

  const submit = (q: string) => {
    const trimmed = q.trim()
    if (trimmed.length < 3 || mutation.isPending) return
    setQuestion(trimmed)
    mutation.mutate(trimmed)
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="panel">
        <h3>Ask about {teamName} (experimental)</h3>
        <p className="sub">
          Answers are generated only from this dashboard's precomputed data — numbers and sample
          sizes are cited, and the assistant will say when the data can't answer. Verify anything
          load-bearing against the views.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submit(question)
          }}
          className="ask-row"
        >
          <input
            className="team-search ask-input"
            placeholder={`e.g. ${SUGGESTIONS[0]}`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            aria-label="Question about the opponent"
          />
          <button className="print-btn" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Thinking…' : 'Ask'}
          </button>
        </form>
        <div className="seg-row" style={{ marginTop: 10 }}>
          {SUGGESTIONS.map((s) => (
            <button key={s} className="seg" onClick={() => submit(s)} disabled={mutation.isPending}>
              {s}
            </button>
          ))}
        </div>
        {mutation.isError && (
          <p className="note" style={{ color: 'var(--shot)' }}>
            {mutation.error instanceof Error ? mutation.error.message : String(mutation.error)}
          </p>
        )}
        {mutation.data && (
          <div className="ask-answer">
            {paragraphs(mutation.data.answer).map((para, i) => (
              <p key={i}>{renderEmphasis(para)}</p>
            ))}
            <div className="ask-meta">answered by {mutation.data.model} · grounded in dashboard data only</div>
          </div>
        )}
      </div>
    </div>
  )
}
