import type { TooltipState } from '../lib/useTooltip'

/** Fixed-position tooltip that follows the pointer; render near the viz root. */
export function TooltipLayer({ tip }: { tip: TooltipState | null }) {
  if (!tip) return null
  const left = Math.min(tip.x + 14, window.innerWidth - 260)
  const top = Math.min(tip.y + 12, window.innerHeight - 120)
  return (
    <div className="viz-tooltip" style={{ left, top }}>
      {tip.content}
    </div>
  )
}
