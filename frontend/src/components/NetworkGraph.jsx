import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'
import { Share2, ArrowRight } from 'lucide-react'
import { api } from '../api/client'

const COLORS = ['#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981','#6366f1','#ef4444','#14b8a6','#f97316','#a855f7','#06b6d4','#84cc16']

function CustomTreemapContent({ x, y, width, height, index, name, value, depth }) {
  if (width < 30 || height < 20 || depth !== 1) return null
  const color = COLORS[index % COLORS.length]
  const showLabel = width > 55 && height > 28
  const showCount = width > 70 && height > 40
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4}
        fill={color} fillOpacity={0.85} stroke="#fff" strokeWidth={2} />
      {showLabel && (
        <text x={x + width / 2} y={y + height / 2 - (showCount ? 5 : 0)} textAnchor="middle"
          dominantBaseline="central" fill="#fff" fontSize={width > 100 ? 12 : 10} fontWeight={600}>
          {name.length > Math.floor(width / 7) ? name.slice(0, Math.floor(width / 7)) + '…' : name}
        </text>
      )}
      {showCount && (
        <text x={x + width / 2} y={y + height / 2 + 12} textAnchor="middle"
          dominantBaseline="central" fill="rgba(255,255,255,0.75)" fontSize={9}>
          {value} connections
        </text>
      )}
    </g>
  )
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload
  return (
    <div className="bg-white/95 backdrop-blur-sm rounded-lg border border-gray-200 px-3 py-2 shadow-lg">
      <div className="text-sm font-semibold text-gray-800">{d.fullName || d.name}</div>
      <div className="text-xs text-gray-400">{d.email}</div>
      <div className="text-xs text-gray-600 mt-1">{d.value} shared thread connections</div>
      {d.emailCount && <div className="text-xs text-gray-400">{d.emailCount} total emails</div>}
    </div>
  )
}

export default function NetworkGraph() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [minShared, setMinShared] = useState(2)

  useEffect(() => {
    setLoading(true)
    api.getNetwork(minShared, 80).then(setData).catch(console.error).finally(() => setLoading(false))
  }, [minShared])

  const treemapData = data?.nodes?.length ? (() => {
    const connCount = {}
    data.edges.forEach(e => {
      connCount[e.source] = (connCount[e.source] || 0) + 1
      connCount[e.target] = (connCount[e.target] || 0) + 1
    })
    const items = data.nodes
      .map(n => ({
        name: n.name?.split(' ')[0] || n.id.split('@')[0],
        fullName: n.name || n.id.split('@')[0],
        email: n.id,
        value: connCount[n.id] || 0,
        emailCount: n.email_count,
      }))
      .filter(n => n.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 40)
    return [{ name: 'Network', children: items }]
  })() : null

  const topPairs = data?.edges?.length ? [...data.edges]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 8)
    .map(e => {
      const src = data.nodes.find(n => n.id === e.source)
      const tgt = data.nodes.find(n => n.id === e.target)
      return {
        source: src?.name?.split(' ')[0] || e.source.split('@')[0],
        sourceEmail: e.source,
        target: tgt?.name?.split(' ')[0] || e.target.split('@')[0],
        targetEmail: e.target,
        weight: e.weight,
      }
    }) : []

  const maxWeight = topPairs.length ? topPairs[0].weight : 1

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Share2 className="w-4 h-4" /> Communication Network
        </h3>
        <label className="text-xs text-gray-400">Min shared threads:
          <select value={minShared} onChange={e => setMinShared(Number(e.target.value))}
            className="ml-1 text-xs border border-gray-200 rounded px-1.5 py-0.5">
            <option value={1}>1+</option><option value={2}>2+</option><option value={3}>3+</option><option value={5}>5+</option><option value={10}>10+</option>
          </select>
        </label>
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="skeleton h-48 rounded-lg" />
          <div className="skeleton h-32 rounded-lg" />
        </div>
      ) : !data?.nodes?.length ? (
        <div className="text-center py-12 text-gray-400 text-sm">No network data. Build threads first to see connections.</div>
      ) : (
        <div className="space-y-5">
          {treemapData?.[0]?.children?.length > 0 && (
            <div>
              <div className="text-xs text-gray-400 mb-2">Contact map — sized by connections</div>
              <ResponsiveContainer width="100%" height={220}>
                <Treemap data={treemapData} dataKey="value" stroke="none"
                  content={<CustomTreemapContent />}>
                  <Tooltip content={<CustomTooltip />} />
                </Treemap>
              </ResponsiveContainer>
            </div>
          )}

          {topPairs.length > 0 && (
            <div>
              <div className="text-xs text-gray-400 mb-2">Strongest connections</div>
              <div className="space-y-1.5">
                {topPairs.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <Link to={'/contact/' + encodeURIComponent(p.sourceEmail)}
                      className="text-gray-700 hover:text-blue-600 truncate min-w-[60px] text-right font-medium">
                      {p.source}
                    </Link>
                    <div className="flex-1 flex items-center gap-1.5">
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all"
                          style={{ width: (p.weight / maxWeight * 100) + '%', backgroundColor: COLORS[i % COLORS.length], opacity: 0.7 }} />
                      </div>
                      <span className="text-[10px] text-gray-400 w-6 text-center">{p.weight}</span>
                    </div>
                    <Link to={'/contact/' + encodeURIComponent(p.targetEmail)}
                      className="text-gray-700 hover:text-blue-600 truncate min-w-[60px] font-medium">
                      {p.target}
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between text-[10px] text-gray-400 pt-2 border-t border-gray-100">
            <span>{data.nodes.length} contacts · {data.edges.length} connections</span>
            <Link to="/contacts" className="flex items-center gap-0.5 hover:text-blue-600">
              View all contacts <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
