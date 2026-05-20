import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BarChart3, Users, Calendar, MessageSquare, Clock, TrendingUp, TrendingDown, Mail, RefreshCw, Layers, Search, Paperclip, ArrowRight, Zap } from 'lucide-react'
import { api } from '../api/client'
import { useChartTheme } from '../hooks/useChartTheme'
import { OnboardingBanner } from './OnboardingTips'

const COLORS = ['#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981','#6366f1']
const DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

const CACHE_KEY = 'quackbox-dashboard-cache'

function getCachedDashboard() {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const cached = JSON.parse(raw)
    if (Date.now() - cached._ts > 300_000) return null
    return cached
  } catch { return null }
}

function setCachedDashboard(data) {
  try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ...data, _ts: Date.now() })) } catch {}
}

export default function Dashboard() {
  const [volume, setVolume] = useState(null)
  const [contacts, setContacts] = useState(null)
  const [heatmap, setHeatmap] = useState(null)
  const [yearly, setYearly] = useState(null)
  const [threadStats, setThreadStats] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)
  const chart = useChartTheme()

  const applyData = (data) => {
    if (data.volume) setVolume(data.volume)
    if (data.contacts) setContacts(data.contacts)
    if (data.heatmap) setHeatmap(data.heatmap)
    if (data.yearly) setYearly(data.yearly)
    if (data.thread_stats) setThreadStats(data.thread_stats)
    if (data.stats) setStats(data.stats)
  }

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    const cached = getCachedDashboard()
    if (cached) {
      applyData(cached)
      setLoading(false)
      setStale(true)
    } else {
      setLoading(true)
    }
    try {
      const data = await api.getDashboard()
      applyData(data)
      setCachedDashboard(data)
      setStale(false)
    } catch (err) {
      console.error('Dashboard load error:', err)
      if (!cached) {
        try {
          const [vol, cont, heat, yr, ts, st] = await Promise.allSettled([
            api.getVolume(), api.getTopContacts(15), api.getHeatmap(),
            api.getYearly(), api.getThreadStats(), api.getStats()])
          if (vol.status === 'fulfilled') setVolume(vol.value.data)
          if (cont.status === 'fulfilled') setContacts(cont.value.data)
          if (heat.status === 'fulfilled') setHeatmap(heat.value.data)
          if (yr.status === 'fulfilled') setYearly(yr.value.data)
          if (ts.status === 'fulfilled') setThreadStats(ts.value.data)
          if (st.status === 'fulfilled') setStats(st.value)
        } catch (e) { console.error(e) }
      }
    } finally {
      setLoading(false)
      setStale(false)
    }
  }

  // Compute volume insights
  const volumeInsights = useMemo(() => {
    if (!volume || volume.length < 2) return null
    const latest = volume[volume.length - 1]
    const prev = volume[volume.length - 2]
    const thisYear = volume.filter(v => v.month.startsWith(latest.month.slice(0,4)))
    const yearTotal = thisYear.reduce((s, v) => s + v.total, 0)
    const busiest = [...volume].sort((a, b) => b.total - a.total)[0]
    const change = prev?.total ? Math.round(((latest.total - prev.total) / prev.total) * 100) : 0
    return { latest, change, yearTotal, busiestMonth: busiest }
  }, [volume])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-600 dark:text-blue-400" />Dashboard
          </h2>
          {stats?.date_range?.earliest && (
            <p className="text-xs text-gray-400 mt-0.5">
              {stats.date_range.earliest.slice(0,10)} → {stats.date_range.latest.slice(0,10)}
            </p>
          )}
        </div>
        <button onClick={() => { sessionStorage.removeItem(CACHE_KEY); loadAll() }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" />Refresh
        </button>
      </div>

      <OnboardingBanner id="dashboard-intro">
        Welcome to QuackBox! This dashboard shows live stats from your email archive.
        Use the sidebar (or tap <strong>More</strong> on mobile) to explore threads, contacts, attachments, and AI-powered features.
      </OnboardingBanner>

      {/* Hero Stat Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <HeroCard icon={Mail} label="Total Emails" value={stats.total_emails?.toLocaleString()}
            gradient="from-blue-500 to-blue-600" accent="blue" />
          <HeroCard icon={Users} label="Unique Senders" value={stats.unique_senders?.toLocaleString()}
            gradient="from-purple-500 to-purple-600" accent="purple" link="/contacts" />
          <HeroCard icon={Layers} label="Mailboxes" value={stats.mbox_sources}
            gradient="from-pink-500 to-rose-600" accent="pink" />
          <HeroCard icon={MessageSquare} label="Threads" value={stats.total_threads?.toLocaleString() || '—'}
            gradient="from-amber-500 to-orange-600" accent="amber" link="/threads"
            sub={!stats.total_threads && 'Build threads →'} />
          <HeroCard icon={Calendar} label="Date Range"
            value={stats.date_range?.earliest ? `${stats.date_range.earliest.slice(0,4)}–${stats.date_range.latest.slice(0,4)}` : '—'}
            gradient="from-emerald-500 to-green-600" accent="green" />
        </div>
      )}

      {/* Volume Chart with Insights Strip */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="px-5 pt-5 pb-2">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />Email Volume
            </h3>
            {volumeInsights && (
              <div className="flex items-center gap-1 text-xs">
                {volumeInsights.change >= 0
                  ? <span className="flex items-center gap-0.5 text-green-600 dark:text-green-300 bg-green-50 dark:bg-green-900/40 px-2 py-0.5 rounded-full"><TrendingUp className="w-3 h-3" />+{volumeInsights.change}%</span>
                  : <span className="flex items-center gap-0.5 text-red-500 dark:text-red-300 bg-red-50 dark:bg-red-900/40 px-2 py-0.5 rounded-full"><TrendingDown className="w-3 h-3" />{volumeInsights.change}%</span>
                }
                <span className="text-gray-400">vs last month</span>
              </div>
            )}
          </div>
        </div>
        {volume ? (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={volume} margin={{ left: 0, right: 0, top: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="vg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={chart.dark ? 0.5 : 0.35}/>
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chart.gridStroke} vertical={false}/>
              <XAxis dataKey="month" {...chart.axisProps} tick={{ ...chart.axisProps.tick, fontSize: 10 }} interval="preserveStartEnd"
                tickFormatter={v=>{const[y,m]=v.split('-');return m==='01'?y:''}} axisLine={false} tickLine={false}/>
              <YAxis {...chart.axisProps} tick={{ ...chart.axisProps.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={40}/>
              <Tooltip {...chart.tooltipProps}
                labelFormatter={v=>{const[y,m]=v.split('-');return new Date(y,m-1).toLocaleString('default',{month:'long',year:'numeric'})}}/>
              <Area type="monotone" dataKey="total" stroke="#3b82f6" fill="url(#vg)" strokeWidth={2}
                dot={false} activeDot={{ r: 4, fill: '#3b82f6', stroke: chart.dark ? '#111827' : '#fff', strokeWidth: 2 }}/>
            </AreaChart>
          </ResponsiveContainer>
        ) : <Skeleton h={260}/>}
        {/* Insights strip */}
        {volumeInsights && (
          <div className="grid grid-cols-3 divide-x divide-gray-100 dark:divide-gray-800 border-t border-gray-100 dark:border-gray-800">
            <InsightChip label="Latest month" value={`${volumeInsights.latest.total.toLocaleString()} emails`} />
            <InsightChip label="Year total" value={`${volumeInsights.yearTotal.toLocaleString()} emails`} />
            <InsightChip label="Busiest month"
              value={`${new Date(volumeInsights.busiestMonth.month + '-01').toLocaleString('default', {month:'short', year:'numeric'})} (${volumeInsights.busiestMonth.total.toLocaleString()})`} />
          </div>
        )}
      </div>

      {/* Two-column: Contacts + Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Contacts */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="px-5 pt-5 pb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2"><Users className="w-4 h-4"/>Top Contacts</h3>
            <Link to="/contacts" className="text-xs text-blue-500 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-0.5">View all<ArrowRight className="w-3 h-3"/></Link>
          </div>
          {contacts ? (
            <div className="divide-y divide-gray-50 dark:divide-gray-800">
              {contacts.slice(0,10).map((c,i)=>{
                const maxTotal = contacts[0]?.total || 1
                return (
                  <Link key={c.email} to={`/contact/${encodeURIComponent(c.email)}`}
                    className="flex items-center gap-3 px-5 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group">
                    <div className="w-5 text-xs text-gray-300 dark:text-gray-600 text-right font-mono">{i+1}</div>
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-sm"
                      style={{backgroundColor:COLORS[i%COLORS.length]}}>
                      {(c.name||c.email).charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate group-hover:text-blue-600 dark:group-hover:text-blue-300 transition-colors">{c.name}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <div className="flex-1 h-1 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden max-w-[120px]">
                          <div className="h-full rounded-full transition-all" style={{
                            width: `${(c.total / maxTotal * 100)}%`,
                            backgroundColor: COLORS[i%COLORS.length],
                            opacity: 0.6,
                          }}/>
                        </div>
                        <span className="text-[10px] text-gray-400">{c.total.toLocaleString()}</span>
                      </div>
                    </div>
                    {c.sparkline?.length > 2 && (
                      <div className="w-16 h-6 opacity-50 group-hover:opacity-100 transition-opacity">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={c.sparkline}>
                            <Area type="monotone" dataKey="count" stroke={COLORS[i%COLORS.length]}
                              fill={COLORS[i%COLORS.length]} fillOpacity={chart.dark ? 0.3 : 0.15} strokeWidth={1.5}/>
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </Link>
                )
              })}
            </div>
          ) : <Skeleton h={420}/>}
        </div>

        {/* Activity Heatmap */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-4 flex items-center gap-2"><Clock className="w-4 h-4"/>Activity Patterns</h3>
          {heatmap ? <HeatGrid data={heatmap} dark={chart.dark}/> : <Skeleton h={420}/>}
        </div>
      </div>

      {/* Year by Year */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="px-5 pt-5 pb-2">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2"><Calendar className="w-4 h-4"/>Year by Year</h3>
        </div>
        {yearly ? (
          <>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={yearly} margin={{ left: 0, right: 16, top: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chart.gridStroke} vertical={false}/>
                <XAxis dataKey="year" {...chart.axisProps} tick={{ ...chart.axisProps.tick, fontSize: 11 }} axisLine={false} tickLine={false}/>
                <YAxis {...chart.axisProps} tick={{ ...chart.axisProps.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={45}/>
                <Tooltip {...chart.tooltipProps}/>
                <Bar dataKey="total_emails" name="Emails" fill="#3b82f6" radius={[6,6,0,0]} maxBarSize={48}/>
                <Bar dataKey="unique_senders" name="Senders" fill="#8b5cf6" radius={[6,6,0,0]} maxBarSize={48}/>
              </BarChart>
            </ResponsiveContainer>
            {/* Year highlights */}
            <div className="grid grid-cols-3 divide-x divide-gray-100 dark:divide-gray-800 border-t border-gray-100 dark:border-gray-800">
              <InsightChip label="Total years" value={yearly.length} />
              <InsightChip label="Peak year"
                value={(() => { const p = [...yearly].sort((a,b) => b.total_emails - a.total_emails)[0]; return p ? `${p.year} (${p.total_emails.toLocaleString()})` : '—' })()} />
              <InsightChip label="Most senders"
                value={(() => { const p = [...yearly].sort((a,b) => b.unique_senders - a.unique_senders)[0]; return p ? `${p.year} (${p.unique_senders.toLocaleString()})` : '—' })()} />
            </div>
          </>
        ) : <Skeleton h={280}/>}
      </div>

      {/* Thread Insights */}
      {threadStats && threadStats.total_threads > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="px-5 pt-5 pb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2"><MessageSquare className="w-4 h-4"/>Thread Insights</h3>
            <Link to="/threads" className="text-xs text-blue-500 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-0.5">Browse threads<ArrowRight className="w-3 h-3"/></Link>
          </div>
          {/* Summary strip */}
          <div className="grid grid-cols-3 divide-x divide-gray-100 dark:divide-gray-800 border-y border-gray-100 dark:border-gray-800">
            <InsightChip label="Total threads" value={threadStats.total_threads.toLocaleString()} />
            <InsightChip label="Conversations" value={threadStats.conversations?.toLocaleString() || '—'} />
            <InsightChip label="Avg length" value={`${threadStats.average_thread_length} msgs`} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-0 divide-y md:divide-y-0 md:divide-x divide-gray-100 dark:divide-gray-800">
            <ThreadColumn title="Longest Threads" icon={<Zap className="w-3 h-3 text-amber-500"/>}
              items={threadStats.longest_threads} subtitle={t => `${t.message_count} msgs · ${t.participant_count} people`}/>
            <ThreadColumn title="Most Participants" icon={<Users className="w-3 h-3 text-purple-500"/>}
              items={threadStats.most_participants} subtitle={t => `${t.participant_count} people · ${t.message_count} msgs`}/>
            <ThreadColumn title="Longest Running" icon={<Clock className="w-3 h-3 text-green-500"/>}
              items={threadStats.longest_duration} subtitle={t => `${Math.round((t.duration_seconds||0)/86400)} days · ${t.message_count} msgs`}/>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <QuickAction to="/search" icon={Search} label="Search Archive" color="blue"/>
        <QuickAction to="/calendar" icon={Calendar} label="Calendar View" color="green"/>
        <QuickAction to="/attachments" icon={Paperclip} label="Attachments" color="amber"/>
        <QuickAction to="/timeline" icon={Clock} label="Timeline" color="purple"/>
      </div>
    </div>
  )
}


// ── Sub-components ──────────────────────────────────────────

function HeroCard({ icon: Icon, label, value, gradient, accent, link, sub }) {
  const inner = (
    <div className="relative overflow-hidden">
      <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${gradient} flex items-center justify-center mb-3 shadow-sm`}>
        <Icon className="w-4.5 h-4.5 text-white" />
      </div>
      <div className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">{value}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{label}</div>
      {sub && <div className="mt-1.5 text-xs text-blue-600 dark:text-blue-400 font-medium">{sub}</div>}
      {/* Decorative circle */}
      <div className={`absolute -right-4 -top-4 w-20 h-20 rounded-full bg-gradient-to-br ${gradient} opacity-[0.06] dark:opacity-[0.12]`}/>
    </div>
  )
  const base = "bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 transition-all duration-200"
  return link
    ? <Link to={link} className={`${base} hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-sm`}>{inner}</Link>
    : <div className={base}>{inner}</div>
}

function InsightChip({ label, value }) {
  return (
    <div className="px-4 py-2.5">
      <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">{value}</div>
    </div>
  )
}

function ThreadColumn({ title, icon, items, subtitle }) {
  return (
    <div className="p-4">
      <div className="text-xs text-gray-400 mb-2 flex items-center gap-1.5 font-medium">
        {icon}{title}
      </div>
      <div className="space-y-1">
        {items?.slice(0,3).map(t => (
          <Link key={t.id} to={`/thread/${t.id}`}
            className="block py-1.5 px-2 -mx-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-lg transition-colors">
            <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">{t.subject_normalized || '(no subject)'}</div>
            <div className="text-[11px] text-gray-400">{subtitle(t)}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}

function QuickAction({ to, icon: Icon, label, color }) {
  const colors = {
    blue: 'hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/50 dark:hover:bg-blue-900/20',
    green: 'hover:border-green-300 dark:hover:border-green-700 hover:bg-green-50/50 dark:hover:bg-green-900/20',
    amber: 'hover:border-amber-300 dark:hover:border-amber-700 hover:bg-amber-50/50 dark:hover:bg-amber-900/20',
    purple: 'hover:border-purple-300 dark:hover:border-purple-700 hover:bg-purple-50/50 dark:hover:bg-purple-900/20',
  }
  const iconColors = {
    blue: 'text-blue-500',
    green: 'text-green-500',
    amber: 'text-amber-500',
    purple: 'text-purple-500',
  }
  return (
    <Link to={to} className={`flex items-center gap-2.5 px-4 py-3 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 transition-all duration-200 group ${colors[color]}`}>
      <Icon className={`w-4 h-4 ${iconColors[color]}`}/>
      <span className="text-sm text-gray-600 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">{label}</span>
      <ArrowRight className="w-3 h-3 text-gray-300 dark:text-gray-600 ml-auto group-hover:text-gray-500 dark:group-hover:text-gray-400 transition-colors"/>
    </Link>
  )
}

function HeatGrid({ data, dark }) {
  const grid = Array.from({length:7}, () => Array(24).fill(0))
  let mx = 1
  data.forEach(({day, hour, count}) => {
    if (day >= 0 && day < 7 && hour >= 0 && hour < 24) {
      grid[day][hour] = count
      if (count > mx) mx = count
    }
  })

  // Heatmap palette — light mode uses blue ramp on near-white, dark mode uses
  // brighter blues on a deep gray base so low-traffic cells stay visible
  const zeroColor = dark ? '#1f2937' : '#f9fafb'
  const palette = dark
    ? ['#1e3a8a', '#1d4ed8', '#3b82f6', '#60a5fa', '#93c5fd']
    : ['#dbeafe', '#93c5fd', '#60a5fa', '#3b82f6', '#2563eb']
  const peakColor = dark ? '#bfdbfe' : '#1d4ed8'

  const getColor = (c) => {
    if (c === 0) return zeroColor
    const i = c / mx
    if (i < 0.15) return palette[0]
    if (i < 0.3) return palette[1]
    if (i < 0.5) return palette[2]
    if (i < 0.7) return palette[3]
    if (i < 0.85) return palette[4]
    return peakColor
  }

  // Find peak hour/day
  let peakDay = 0, peakHour = 0, peakCount = 0
  grid.forEach((row, d) => row.forEach((c, h) => { if (c > peakCount) { peakDay = d; peakHour = h; peakCount = c } }))
  const totalEmails = data.reduce((s, d) => s + d.count, 0)

  return (
    <div>
      <div className="flex ml-10 mb-1">
        {Array.from({length:24}, (_,h) => (
          <div key={h} className="flex-1 text-center text-[9px] text-gray-400">{h % 4 === 0 ? `${h}:00` : ''}</div>
        ))}
      </div>
      {DAYS.map((day, d) => (
        <div key={d} className="flex items-center gap-1 mb-0.5">
          <div className="w-9 text-xs text-gray-500 dark:text-gray-400 text-right pr-1 font-medium">{day}</div>
          <div className="flex flex-1 gap-0.5">
            {grid[d].map((count, h) => (
              <div key={h} className="flex-1 rounded-[3px] aspect-square transition-colors"
                style={{backgroundColor: getColor(count), minHeight: '14px'}}
                title={`${day} ${h}:00 — ${count.toLocaleString()} emails`}/>
            ))}
          </div>
        </div>
      ))}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-1 text-[10px] text-gray-400">
          <span>Less</span>
          {[zeroColor, ...palette, peakColor].map((c,i) => (
            <div key={i} className="w-3 h-3 rounded-sm" style={{backgroundColor:c}}/>
          ))}
          <span>More</span>
        </div>
        <div className="text-[10px] text-gray-400">
          Peak: <span className="font-medium text-gray-600 dark:text-gray-300">{DAYS[peakDay]} {peakHour}:00</span>
          <span className="mx-1">·</span>
          {totalEmails.toLocaleString()} total
        </div>
      </div>
    </div>
  )
}

function Skeleton({ h }) {
  return (
    <div className="flex items-center justify-center rounded-lg" style={{height: h}}>
      <div className="flex flex-col items-center gap-2">
        <div className="w-6 h-6 border-2 border-gray-200 dark:border-gray-700 border-t-blue-500 rounded-full animate-spin"/>
        <span className="text-xs text-gray-400">Loading...</span>
      </div>
    </div>
  )
}
