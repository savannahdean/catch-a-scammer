// Evidence Map: the pinned records and their immediate neighbours, as a graph.
//
// The server sends untyped (src, dst, label) edges from the one generalized
// relationship table; this window lays them out with a small force simulation
// (every pair repels, edges pull like springs, a weak pull to the centre) and
// knows nothing about what a domain or a wallet is beyond its colour.
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import type { PointerEvent, WheelEvent } from 'react'
import { api } from '../api/client'
import type { GraphEdge, GraphNode } from '../api/types'
import { useSession } from '../state/session'
import { appForKind, kindColor, kindLabel, statusColor } from '../theme'
import { Badge, Notice } from '../ui/widgets'
import type { AppProps } from './types'

interface Body {
  x: number
  y: number
  vx: number
  vy: number
}

const NODE_H = 34
const CHAR_W = 7.3 // 12px monospace
const MAX_W = 250
const nodeW = (n: GraphNode) => Math.min(MAX_W, Math.max(110, n.label.length * CHAR_W + 22))
const fit = (label: string) => {
  const max = Math.floor((MAX_W - 22) / CHAR_W)
  return label.length > max ? label.slice(0, max - 1) + '…' : label
}
const PINNED = '#e8b23f' // SVG attributes can't read CSS variables, so colours here are literal

const LEGEND = ['domain', 'ip', 'certificate', 'malware_family', 'persona', 'phone', 'payment_account', 'campaign',
  'threat_actor', 'person']

export function EvidenceMap({ signal, active }: AppProps) {
  const s = useSession()
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  const [, redraw] = useReducer((x: number) => x + 1, 0)
  const bodies = useRef(new Map<string, Body>())
  const heat = useRef(0)
  const drag = useRef<{ id: string | null; panFrom?: { x: number; y: number; vx: number; vy: number } } | null>(null)
  const svg = useRef<SVGSVGElement>(null)

  const load = useCallback(async () => {
    if (s.caseId == null) return
    try {
      const g = await api.graph(s.caseId)
      const next = new Map<string, Body>()
      g.nodes.forEach((n, i) => {
        const old = bodies.current.get(n.node_id)
        const a = i * 2.399963
        const r = 60 + 14 * i
        next.set(n.node_id, old ?? { x: Math.cos(a) * r, y: Math.sin(a) * r, vx: 0, vy: 0 })
      })
      bodies.current = next
      setNodes(g.nodes)
      setEdges(g.edges)
      heat.current = 260
    } catch (e) {
      s.notify(`Could not load the evidence map: ${e instanceof Error ? e.message : e}`, true)
    }
  }, [s.caseId, s.notify])

  useEffect(() => {
    void load()
  }, [load, signal?.nonce, s.evidence.length])

  // the simulation runs for a few seconds after anything changes, then rests
  useEffect(() => {
    let frame = 0
    const step = () => {
      if (heat.current > 0 && active) {
        heat.current -= 1
        simulate(bodies.current, nodes, edges, drag.current?.id ?? null)
        redraw()
      }
      frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [nodes, edges, active])

  const toWorld = (clientX: number, clientY: number) => {
    const r = svg.current!.getBoundingClientRect()
    return { x: (clientX - r.left - r.width / 2 - view.x) / view.k, y: (clientY - r.top - r.height / 2 - view.y) / view.k }
  }

  const onNodeDown = (e: PointerEvent, id: string) => {
    e.stopPropagation()
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
    setSelected(id)
    drag.current = { id }
  }
  const onBgDown = (e: PointerEvent) => {
    setSelected(null)
    drag.current = { id: null, panFrom: { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y } }
  }
  const onMove = (e: PointerEvent) => {
    const d = drag.current
    if (!d) return
    if (d.id) {
      const b = bodies.current.get(d.id)
      if (!b) return
      const w = toWorld(e.clientX, e.clientY)
      b.x = w.x
      b.y = w.y
      b.vx = b.vy = 0
      heat.current = Math.max(heat.current, 90)
      redraw()
    } else if (d.panFrom) {
      setView({ ...view, x: d.panFrom.vx + e.clientX - d.panFrom.x, y: d.panFrom.vy + e.clientY - d.panFrom.y })
    }
  }
  const onUp = () => {
    drag.current = null
  }
  const onWheel = (e: WheelEvent) => {
    setView((v) => ({ ...v, k: Math.min(2.4, Math.max(0.3, v.k * (e.deltaY < 0 ? 1.1 : 0.9))) }))
  }

  if (s.caseId == null) return <div className="app"><div className="app-body"><Notice>No case is open.</Notice></div></div>

  const byId = new Map(nodes.map((n) => [n.node_id, n]))
  const sel = selected ? byId.get(selected) : undefined

  return (
    <div className="app evidencemap">
      <div className="map-bar">
        <span>
          {nodes.length} records · {edges.length} links · {s.evidence.length} pinned
        </span>
        <span className="dim">drag to pan · scroll to zoom · drag a node to move it</span>
        <button type="button" className="btn btn-small" onClick={() => void load()}>
          REFRESH
        </button>
        <button type="button" className="btn btn-small" onClick={() => setView({ x: 0, y: 0, k: 1 })}>
          RECENTER
        </button>
      </div>
      <div className="map-main">
        {nodes.length === 0 ? (
          <div className="map-empty">
            Nothing pinned yet. Use ADD TO EVIDENCE on a record and it appears here with everything it connects to.
          </div>
        ) : (
          <svg
            ref={svg}
            className="map-svg"
            onPointerDown={onBgDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerLeave={onUp}
            onWheel={onWheel}
          >
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.035)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
            <g transform={`translate(${(svg.current?.clientWidth ?? 0) / 2 + view.x} ${(svg.current?.clientHeight ?? 0) / 2 + view.y}) scale(${view.k})`}>
              {edges.map((e, i) => {
                const a = bodies.current.get(e.src)
                const b = bodies.current.get(e.dst)
                if (!a || !b) return null
                const touched = selected === e.src || selected === e.dst
                return (
                  <g key={i} opacity={touched ? 1 : 0.35 + 0.5 * e.confidence}>
                    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`map-edge${touched ? ' touched' : ''}`} />
                    {(touched || view.k > 1.2) && (
                      <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} className="map-edge-label">
                        {e.label}
                      </text>
                    )}
                  </g>
                )
              })}
              {nodes.map((n) => {
                const b = bodies.current.get(n.node_id)
                if (!b) return null
                const w = nodeW(n)
                const color = kindColor(n.kind)
                return (
                  <g
                    key={n.node_id}
                    transform={`translate(${b.x - w / 2} ${b.y - NODE_H / 2})`}
                    className={`map-node${selected === n.node_id ? ' selected' : ''}`}
                    onPointerDown={(e) => onNodeDown(e, n.node_id)}
                  >
                    <rect width={w} height={NODE_H} rx={5} className="map-node-box" stroke={n.in_evidence ? PINNED : color}
                      strokeWidth={n.in_evidence ? 2.4 : 1.4} />
                    <rect width={4} height={NODE_H} fill={color} />
                    <text x={10} y={12} className="map-node-kind" fill={color}>
                      {kindLabel(n.kind)}{n.in_evidence ? '  ★ PINNED' : ''}
                    </text>
                    <text x={10} y={26} className="map-node-label">
                      {fit(n.label)}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        )}
        <aside className="map-side">
          {sel ? (
            <>
              <Badge color={kindColor(sel.kind)}>{kindLabel(sel.kind)}</Badge>
              <div className="map-side-title">{sel.label}</div>
              <div className="dim small">{sel.sublabel}</div>
              {sel.status && (
                <div className="small" style={{ color: statusColor(sel.status) }}>
                  status: {sel.status}
                </div>
              )}
              <div className="dim small">{sel.in_evidence ? 'Pinned as evidence' : 'Not pinned: a neighbour of your evidence'}</div>
              <button type="button" className="btn" onClick={() => s.requestOpen(appForKind(sel.kind), sel.query)}>
                OPEN IN TOOL
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={s.isPinned(sel.entity_id) || s.brief?.status !== 'open'}
                onClick={() => void s.pin({ entity_kind: sel.kind, entity_id: sel.entity_id, label: sel.label })}
              >
                {s.isPinned(sel.entity_id) ? 'IN EVIDENCE' : 'ADD TO EVIDENCE'}
              </button>
              <div className="map-side-links">
                {edges
                  .filter((e) => e.src === sel.node_id || e.dst === sel.node_id)
                  .map((e, i) => {
                    const other = byId.get(e.src === sel.node_id ? e.dst : e.src)
                    return (
                      <button key={i} type="button" className="link-btn" onClick={() => other && setSelected(other.node_id)}>
                        {e.src === sel.node_id ? '→' : '←'} {e.label}: {other?.label}
                      </button>
                    )
                  })}
              </div>
            </>
          ) : (
            <>
              <div className="eyebrow">EVIDENCE MAP</div>
              <p className="small dim">
                Select a node to see what it links to. Gold borders are pinned evidence. Evidence doesn't mean correct:
                a linked record can still be a decoy.
              </p>
              <div className="legend">
                {LEGEND.map((k) => (
                  <div key={k} className="legend-item">
                    <span className="legend-dot" style={{ background: kindColor(k) }} />
                    {kindLabel(k)}
                  </div>
                ))}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

function simulate(bodies: Map<string, Body>, nodes: GraphNode[], edges: GraphEdge[], held: string | null) {
  const dt = 0.033
  const list = nodes.map((n) => [n.node_id, bodies.get(n.node_id)!] as const).filter(([, b]) => b)
  for (let i = 0; i < list.length; i++) {
    for (let j = i + 1; j < list.length; j++) {
      const a = list[i][1]
      const b = list[j][1]
      const dx = b.x - a.x
      const dy = b.y - a.y
      const d2 = dx * dx + dy * dy + 0.01
      const d = Math.sqrt(d2)
      const f = Math.min(46000 / d2, 900)
      a.vx -= (dx / d) * f * dt
      a.vy -= (dy / d) * f * dt
      b.vx += (dx / d) * f * dt
      b.vy += (dy / d) * f * dt
    }
  }
  for (const e of edges) {
    const a = bodies.get(e.src)
    const b = bodies.get(e.dst)
    if (!a || !b) continue
    const dx = b.x - a.x
    const dy = b.y - a.y
    const d = Math.sqrt(dx * dx + dy * dy) + 0.01
    const f = (d - 170) * 1.9
    a.vx += (dx / d) * f * dt
    a.vy += (dy / d) * f * dt
    b.vx -= (dx / d) * f * dt
    b.vy -= (dy / d) * f * dt
  }
  for (const [id, b] of list) {
    b.vx = (b.vx - b.x * 0.55 * dt) * 0.86
    b.vy = (b.vy - b.y * 0.55 * dt) * 0.86
    if (id === held) continue
    b.x += b.vx * dt
    b.y += b.vy * dt
  }
}
