import type { ReactNode } from 'react'

/**
 * SVG football pitch in StatsBomb coordinates (120x80, attack left → right,
 * y = 0 is the attacking team's left, drawn at the top as analysts expect).
 * Children are rendered in pitch coordinates on top of the markings.
 */
export function Pitch({
  children,
  showDirection = true,
  half = false,
}: {
  children?: ReactNode
  showDirection?: boolean
  half?: boolean
}) {
  const line = 'var(--pitch-line)'
  const viewBox = half ? '58 -2 64 88' : '-2 -2 124 88'
  return (
    <svg
      viewBox={viewBox}
      style={{ width: '100%', display: 'block', background: 'var(--pitch)', borderRadius: 8 }}
      role="img"
      aria-label="football pitch"
    >
      {children}
      <g stroke={line} strokeWidth={0.35} fill="none" pointerEvents="none">
        <rect x={0} y={0} width={120} height={80} />
        <line x1={60} y1={0} x2={60} y2={80} />
        <circle cx={60} cy={40} r={10} />
        {/* penalty areas */}
        <rect x={0} y={18} width={18} height={44} />
        <rect x={102} y={18} width={18} height={44} />
        {/* six-yard boxes */}
        <rect x={0} y={30} width={6} height={20} />
        <rect x={114} y={30} width={6} height={20} />
        {/* penalty arcs */}
        <path d="M 18 32.8 A 10 10 0 0 1 18 47.2" />
        <path d="M 102 32.8 A 10 10 0 0 0 102 47.2" />
        {/* goals */}
        <rect x={-1.5} y={36} width={1.5} height={8} />
        <rect x={120} y={36} width={1.5} height={8} />
      </g>
      <circle cx={12} cy={40} r={0.5} fill={line} pointerEvents="none" />
      <circle cx={108} cy={40} r={0.5} fill={line} pointerEvents="none" />
      {showDirection && (
        <g transform="translate(53, 83.6)" opacity={0.75}>
          <line x1={0} y1={0} x2={12} y2={0} stroke="var(--muted)" strokeWidth={0.3} />
          <path d="M 12 0 l -1.6 -1 v 2 z" fill="var(--muted)" />
          <text x={-1.5} y={1} fontSize={2.6} fill="var(--muted)" textAnchor="end">
            attack
          </text>
        </g>
      )}
    </svg>
  )
}
