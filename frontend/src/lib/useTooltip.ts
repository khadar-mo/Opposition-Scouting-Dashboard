import { useState, type ReactNode } from 'react'

export interface TooltipState {
  x: number
  y: number
  content: ReactNode
}

export function useTooltip() {
  const [tip, setTip] = useState<TooltipState | null>(null)
  const show = (e: { clientX: number; clientY: number }, content: ReactNode) =>
    setTip({ x: e.clientX, y: e.clientY, content })
  const hide = () => setTip(null)
  return { tip, show, hide }
}
