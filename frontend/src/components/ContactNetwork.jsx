import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Share2, ZoomIn, ZoomOut, RotateCcw, Maximize2 } from 'lucide-react'
import { api } from '../api/client'

/**
 * Force-directed contact network graph rendered in plain SVG.
 *
 * The simulation is a small Verlet integrator with three forces:
 *   - Coulomb-like repulsion between every pair of nodes
 *   - Hooke spring attraction along each edge (weight-scaled)
 *   - Mild center pull so disconnected components don't drift away
 *
 * Bounded at ~150 nodes — the API caps at 80 by default — so brute-force
 * O(n²) repulsion is fine. No d3 dependency.
 */

const NODE_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
  '#6366f1', '#ef4444', '#14b8a6', '#f97316', '#a855f7',
]

// Simulation parameters — tuned for ~80 nodes in a 900x600 viewport
const SIM = {
  repulsion: 4500,      // node-node Coulomb constant
  springLength: 110,    // ideal edge length
  springK: 0.04,        // spring stiffness
  centerPull: 0.005,    // pull every node toward center
  damping: 0.75,        // velocity decay each tick
  maxVelocity: 12,      // clamp so the graph doesn't explode
  ticks: 300,           // how many iterations to run before settling
}

function buildSimulation(nodes, edges, width, height) {
  // Initialize positions on a circle so the simulation has somewhere to push
  const cx = width / 2
  const cy = height / 2
  const radius = Math.min(width, height) * 0.35
  const items = nodes.map((n, i) => {
    const angle = (i / nodes.length) * Math.PI * 2
    return {
      id: n.id,
      name: n.name || n.id,
      emailCount: n.email_count || 0,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0, vy: 0,
      degree: 0,
    }
  })
  const byId = new Map(items.map(it => [it.id, it]))
  const links = edges.map(e => ({
    source: byId.get(e.source),
    target: byId.get(e.target),
    weight: e.weight,
  })).filter(l => l.source && l.target)

  // Pre-compute degree (used for node size)
  links.forEach(l => { l.source.degree += 1; l.target.degree += 1 })

  for (let tick = 0; tick < SIM.ticks; tick++) {
    // Repulsion (every pair)
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j]
        let dx = b.x - a.x, dy = b.y - a.y
        let dist2 = dx * dx + dy * dy
        if (dist2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; dist2 = 1 }
        const force = SIM.repulsion / dist2
        const dist = Math.sqrt(dist2)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        a.vx -= fx; a.vy -= fy
        b.vx += fx; b.vy += fy
      }
    }

    // Spring attraction (edges)
    for (const link of links) {
      const dx = link.target.x - link.source.x
      const dy = link.target.y - link.source.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      // Heavier edges → shorter ideal length → tighter pull
      const ideal = Math.max(40, SIM.springLength - link.weight * 5)
      const displacement = dist - ideal
      const force = SIM.springK * displacement
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      link.source.vx += fx; link.source.vy += fy
      link.target.vx -= fx; link.target.vy -= fy
    }

    // Center pull + integrate
    for (const it of items) {
      it.vx += (cx - it.x) * SIM.centerPull
      it.vy += (cy - it.y) * SIM.centerPull
      it.vx *= SIM.damping
      it.vy *= SIM.damping
      const speed = Math.sqrt(it.vx * it.vx + it.vy * it.vy)
      if (speed > SIM.maxVelocity) {
        it.vx = (it.vx / speed) * SIM.maxVelocity
        it.vy = (it.vy / speed) * SIM.maxVelocity
      }
      it.x += it.vx; it.y += it.vy
    }
  }

  return { nodes: items, links }
}

export default function ContactNetwork() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [minShared, setMinShared] = useState(2)
  const [limit, setLimit] = useState(80)
  const [hovered, setHovered] = useState(null)
  const [transform, setTransform] = useState({ scale: 1, dx: 0, dy: 0 })
  const containerRef = useRef(null)
  const dragRef = useRef(null)
  const navigate = useNavigate()

  const W = 1100
  const H = 640

  useEffect(() => {
    setLoading(true)
    api.getNetwork(minShared, limit)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [minShared, limit])

  const sim = data?.nodes?.length
    ? buildSimulation(data.nodes, data.edges || [], W, H)
    : null

  const maxDegree = sim ? Math.max(1, ...sim.nodes.map(n => n.degree)) : 1
  const maxWeight = sim ? Math.max(1, ...sim.links.map(l => l.weight)) : 1

  const reset = () => setTransform({ scale: 1, dx: 0, dy: 0 })
  const zoom = (factor) => setTransform(t => ({ ...t, scale: Math.max(0.3, Math.min(3, t.scale * factor)) }))

  const onMouseDown = (e) => {
    dragRef.current = { x: e.clientX, y: e.clientY, dx: transform.dx, dy: transform.dy }
  }
  const onMouseMove = useCallback((e) => {
    if (!dragRef.current) return
    setTransform(t => ({
      ...t,
      dx: dragRef.current.dx + (e.clientX - dragRef.current.x),
      dy: dragRef.current.dy + (e.clientY - dragRef.current.y),
    }))
  }, [])
  const onMouseUp = () => { dragRef.current = null }

  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [onMouseMove])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Share2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          Communication Network
          {data?.nodes?.length > 0 && (
            <span className="text-sm font-normal text-gray-400">
              ({data.nodes.length} contacts · {data.edges?.length || 0} connections)
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
            Min shared threads
            <select value={minShared} onChange={e => setMinShared(Number(e.target.value))}
              className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white rounded-lg px-2 py-1">
              <option value={1}>1+</option>
              <option value={2}>2+</option>
              <option value={3}>3+</option>
              <option value={5}>5+</option>
              <option value={10}>10+</option>
            </select>
          </label>
          <label className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
            Top
            <select value={limit} onChange={e => setLimit(Number(e.target.value))}
              className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white rounded-lg px-2 py-1">
              <option value={40}>40</option>
              <option value={80}>80</option>
              <option value={120}>120</option>
              <option value={150}>150</option>
            </select>
          </label>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 dark:border-gray-800">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {hovered
              ? <span><strong className="text-gray-700 dark:text-gray-200">{hovered.name}</strong> · {hovered.emailCount.toLocaleString()} emails · {hovered.degree} connections</span>
              : <span>Drag to pan, scroll/buttons to zoom, click a node to open the contact</span>}
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => zoom(0.8)} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500" title="Zoom out">
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] text-gray-400 w-10 text-center">{Math.round(transform.scale * 100)}%</span>
            <button onClick={() => zoom(1.25)} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500" title="Zoom in">
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button onClick={reset} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500" title="Reset view">
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center" style={{ height: H }}>
            <div className="w-6 h-6 border-2 border-gray-200 dark:border-gray-700 border-t-blue-500 rounded-full animate-spin" />
          </div>
        ) : !sim || sim.nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center gap-3 px-6" style={{ height: H }}>
            <Share2 className="w-10 h-10 text-gray-300 dark:text-gray-700" />
            <p className="text-sm font-medium text-gray-600 dark:text-gray-300">No network connections found.</p>
            <p className="text-xs text-gray-400 max-w-md">
              The graph builds from <em>shared threads</em> — pairs of people who have appeared together
              in the same email conversation. Build threads on the Threads page first, or lower the
              "Min shared threads" filter.
            </p>
          </div>
        ) : (
          <div ref={containerRef}
            className="relative cursor-grab active:cursor-grabbing select-none"
            style={{ height: H, background: 'transparent' }}
            onMouseDown={onMouseDown}>
            <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
              <g transform={`translate(${transform.dx}, ${transform.dy}) scale(${transform.scale})`}>
                {/* Edges first so nodes overlap them */}
                {sim.links.map((l, i) => {
                  const opacity = 0.15 + (l.weight / maxWeight) * 0.55
                  const stroke = (hovered && (hovered.id === l.source.id || hovered.id === l.target.id))
                    ? '#3b82f6'
                    : 'currentColor'
                  return (
                    <line key={i}
                      x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
                      className="text-gray-300 dark:text-gray-700"
                      stroke={stroke}
                      strokeWidth={Math.max(0.7, Math.sqrt(l.weight) * 0.7)}
                      strokeOpacity={opacity}
                    />
                  )
                })}
                {/* Nodes */}
                {sim.nodes.map((n, i) => {
                  const r = 5 + Math.sqrt(n.degree / maxDegree) * 14
                  const color = NODE_COLORS[i % NODE_COLORS.length]
                  const isHovered = hovered?.id === n.id
                  return (
                    <g key={n.id}
                      onMouseEnter={() => setHovered(n)}
                      onMouseLeave={() => setHovered(null)}
                      onClick={() => navigate(`/contact/${encodeURIComponent(n.id)}`)}
                      style={{ cursor: 'pointer' }}>
                      <circle cx={n.x} cy={n.y} r={r}
                        fill={color}
                        fillOpacity={isHovered ? 1 : 0.85}
                        stroke={isHovered ? '#fff' : color}
                        strokeWidth={isHovered ? 3 : 1}
                      />
                      {(isHovered || r > 12) && (
                        <text x={n.x} y={n.y + r + 12} textAnchor="middle"
                          className="fill-gray-700 dark:fill-gray-300 pointer-events-none"
                          fontSize={isHovered ? 12 : 10}
                          fontWeight={isHovered ? 600 : 500}>
                          {(n.name || n.id).split(' ')[0].slice(0, 18)}
                        </text>
                      )}
                    </g>
                  )
                })}
              </g>
            </svg>
            {hovered && (
              <div className="absolute pointer-events-none bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg px-3 py-2 text-xs"
                style={{
                  left: Math.min(W - 200, hovered.x * transform.scale + transform.dx + 12),
                  top: Math.max(0, hovered.y * transform.scale + transform.dy - 40),
                }}>
                <div className="font-semibold text-gray-800 dark:text-gray-200">{hovered.name}</div>
                <div className="text-gray-400 truncate max-w-[200px]">{hovered.id}</div>
                <div className="text-gray-600 dark:text-gray-300 mt-0.5">
                  {hovered.emailCount.toLocaleString()} emails · {hovered.degree} connections
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
