import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import {
  BarChart3, Users, Calendar, MessageSquare, Clock,
  TrendingUp, Mail, RefreshCw, Layers
} from 'lucide-react'
import { api } from '../api/client'

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#6366f1']
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export default function Dashboard() {
  const [volume, setVolume] = useState(null)
  const [contacts, setContacts] = useState(null)
  const [heatmap, setHeatmap] = useState(null)
  const [yearly, setYearly] = useState(null)
  const [threadStats, setThreadStats] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [vol, cont, heat, yr, ts, st] = await Promise.allSettled([
        api.getVolume(),
        api.getTopContacts(15),
        api.getHeatmap(),
        api.getYearly(),
        api.getThreadStats(),
        api.getStats(),
      ])
      if (vol.status === 'fulfilled') setVolume(vol.value.data)
      if (cont.status === 'fulfilled') setContacts(cont.value.data)
      if (heat.status === 'fulfilled') setHeatmap(heat.value.data)
      if (yr.status === 'fulfilled') setYearly(yr.value.data)
      if (ts.status === 'fulfilled') setThreadStats(ts.value.data)
      if (st.status === 'fulfilled') setStats(st.value)
    } catch (err) {
      console.error('Dashboard load error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-600" />
          Dashboard
        </h2>
        <button onClick={loadAll} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 rounded-lg hover:bg-gray-200">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Summary cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard icon={Mail} label="Total Emails" value={stats.total_emails?.toLocaleString()} color="blue" />
          <StatCard icon={Users} label="Unique Senders" value={stats.unique_senders?.toLocaleString()} color="purple" />
          <StatCard icon={Layers} label="Mailboxes" value={stats.mbox_sources} color="pink" />
          <StatCard icon={MessageSquare} label="Threads" value={stats.total_threads?.toLocaleString() || '—'} color="amber"
            sub={stats.total_threads ? null : <Link to="/threads" className="text-blue-600 text-xs">Build threads →</Link>} />
          <StatCard icon={Calendar} label="Date Range"
            value={stats.date_range?.earliest ? `${stats.date_range.earliest.slice(0,4)}–${stats.date_range.latest.slice(0,4)}` : '—'}
            color="green" />
        </div>
      )}

      {/* Volume chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" /> Email Volume Over Time
        </h3>
        {volume ? (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={volume}>
              <defs>
                <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                tickFormatter={(v) => { const [y, m] = v.split('-'); return m === '01' ? y : '' }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip labelFormatter={(v) => {
                const [y, m] = v.split('-')
                return new Date(y, m - 1).toLocaleString('default', { month: 'long', year: 'numeric' })
              }} />
              <Area type="monotone" dataKey="total" stroke="#3b82f6" fill="url(#volGrad)" strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        ) : <Skeleton h={280} />}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top contacts */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Users className="w-4 h-4" /> Top Contacts
          </h3>
          {contacts ? (
            <div className="space-y-2">
              {contacts.slice(0, 12).map((c, i) => (
                <div key={c.email} className="flex items-center gap-3">
                  <div className="w-5 text-xs text-gray-400 text-right">{i + 1}</div>
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium text-white"
                    style={{ backgroundColor: COLORS[i % COLORS.length] }}>
                    {(c.name || c.email).charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800 truncate">{c.name}</div>
                    <div className="text-xs text-gray-400 truncate">{c.email}</div>
                  </div>
                  <div className="text-sm font-semibold text-gray-600">{c.total.toLocaleString()}</div>
                  {/* Mini sparkline */}
                  {c.sparkline?.length > 2 && (
                    <div className="w-20 h-6">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={c.sparkline}>
                          <Area type="monotone" dataKey="count" stroke={COLORS[i % COLORS.length]}
                            fill={COLORS[i % COLORS.length]} fillOpacity={0.2} strokeWidth={1} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : <Skeleton h={400} />}
        </div>

        {/* Activity heatmap */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Activity Patterns
          </h3>
          {heatmap ? <HeatmapGrid data={heatmap} /> : <Skeleton h={400} />}
        </div>
      </div>

      {/* Yearly summary */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <Calendar className="w-4 h-4" /> Year by Year
        </h3>
        {yearly ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={yearly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="year" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="total_emails" name="Emails" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="unique_senders" name="Senders" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : <Skeleton h={250} />}
      </div>

      {/* Thread stats */}
      {threadStats && threadStats.total_threads > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" /> Thread Insights
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-gray-400 mb-2">Longest Threads</div>
              {threadStats.longest_threads?.slice(0, 3).map((t, i) => (
                <Link key={t.id} to={`/thread/${t.id}`} className="block py-1.5 hover:bg-gray-50 rounded px-2">
                  <div className="text-sm font-medium text-gray-700 truncate">{t.subject_normalized || '(no subject)'}</div>
                  <div className="text-xs text-gray-400">{t.message_count} messages, {t.participant_count} people</div>
                </Link>
              ))}
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-2">Most Participants</div>
              {threadStats.most_participants?.slice(0, 3).map((t, i) => (
                <Link key={t.id} to={`/thread/${t.id}`} className="block py-1.5 hover:bg-gray-50 rounded px-2">
                  <div className="text-sm font-medium text-gray-700 truncate">{t.subject_normalized || '(no subject)'}</div>
                  <div className="text-xs text-gray-400">{t.participant_count} people, {t.message_count} messages</div>
                </Link>
              ))}
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-2">Longest Running</div>
              {threadStats.longest_duration?.slice(0, 3).map((t, i) => {
                const days = Math.round((t.duration_seconds || 0) / 86400)
                return (
                  <Link key={t.id} to={`/thread/${t.id}`} className="block py-1.5 hover:bg-gray-50 rounded px-2">
                    <div className="text-sm font-medium text-gray-700 truncate">{t.subject_normalized || '(no subject)'}</div>
                    <div className="text-xs text-gray-400">{days} days, {t.message_count} messages</div>
                  </Link>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color, sub }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    purple: 'bg-purple-50 text-purple-600',
    pink: 'bg-pink-50 text-pink-600',
    amber: 'bg-amber-50 text-amber-600',
    green: 'bg-green-50 text-green-600',
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className={`w-8 h-8 rounded-lg ${colors[color]} flex items-center justify-center mb-2`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="text-xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
      {sub && <div className="mt-1">{sub}</div>}
    </div>
  )
}

function HeatmapGrid({ data }) {
  // Build 7x24 grid
  const grid = Array.from({ length: 7 }, () => Array(24).fill(0))
  let maxCount = 1
  data.forEach(({ day, hour, count }) => {
    if (day >= 0 && day < 7 && hour >= 0 && hour < 24) {
      grid[day][hour] = count
      if (count > maxCount) maxCount = count
    }
  })

  const getColor = (count) => {
    if (count === 0) return '#f9fafb'
    const intensity = count / maxCount
    if (intensity < 0.25) return '#dbeafe'
    if (intensity < 0.5) return '#93c5fd'
    if (intensity < 0.75) return '#3b82f6'
    return '#1d4ed8'
  }

  return (
    <div>
      {/* Hour labels */}
      <div className="flex ml-10 mb-1">
        {Array.from({ length: 24 }, (_, h) => (
          <div key={h} className="flex-1 text-center text-[9px] text-gray-400">
            {h % 3 === 0 ? `${h}` : ''}
          </div>
        ))}
      </div>
      {/* Grid rows */}
      {DAYS.map((day, d) => (
        <div key={d} className="flex items-center gap-1 mb-0.5">
          <div className="w-9 text-xs text-gray-500 text-right pr-1">{day}</div>
          <div className="flex flex-1 gap-0.5">
            {grid[d].map((count, h) => (
              <div
                key={h}
                className="flex-1 rounded-sm aspect-square"
                style={{ backgroundColor: getColor(count), minHeight: '14px' }}
                title={`${day} ${h}:00 — ${count} emails`}
              />
            ))}
          </div>
        </div>
      ))}
      {/* Legend */}
      <div className="flex items-center justify-end gap-1 mt-2 text-[10px] text-gray-400">
        <span>Less</span>
        {['#f9fafb', '#dbeafe', '#93c5fd', '#3b82f6', '#1d4ed8'].map((c, i) => (
          <div key={i} className="w-3 h-3 rounded-sm" style={{ backgroundColor: c }} />
        ))}
        <span>More</span>
      </div>
    </div>
  )
}

function Skeleton({ h }) {
  return (
    <div className="flex items-center justify-center bg-gray-50 rounded-lg" style={{ height: h }}>
      <div className="text-sm text-gray-400">Loading...</div>
    </div>
  )
}
