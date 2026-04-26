import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Layers, ArrowLeft, Mail, Users, Clock, Paperclip, MessageSquare, Download } from 'lucide-react'
import { api } from '../api/client'
import { useChartTheme } from '../hooks/useChartTheme'
import ImportStatus from './ImportStatus'

const COLORS = ['#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981','#6366f1','#ef4444','#14b8a6']

export function MailboxList() {
  const [mailboxes, setMailboxes] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState('count')

  useEffect(() => {
    setLoading(true)
    api.getMailboxBreakdown()
      .then(d => setMailboxes(d.data || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const sorted = mailboxes ? [...mailboxes].sort((a, b) => {
    if (sortBy === 'count') return b.count - a.count
    if (sortBy === 'name') return (a.mbox_source || '').localeCompare(b.mbox_source || '')
    if (sortBy === 'recent') return (b.last_date || '').localeCompare(a.last_date || '')
    return 0
  }) : []

  const maxCount = sorted.length ? Math.max(...sorted.map(m => m.count)) : 1

  return (
    <div className="space-y-6">
      {/* Import source status panel */}
      <ImportStatus />

      <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Layers className="w-5 h-5 text-blue-600 dark:text-blue-400" /> Mailboxes
          {sorted.length > 0 && <span className="text-sm font-normal text-gray-400">({sorted.length})</span>}
        </h2>
        <div className="flex items-center gap-3">
          <select value={sortBy} onChange={e => setSortBy(e.target.value)}
            className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white rounded-lg px-2 py-1.5">
            <option value="count">Most Emails</option>
            <option value="name">Name A-Z</option>
            <option value="recent">Most Recent</option>
          </select>
          <a href="/api/export/emails" download
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700">
            <Download className="w-3.5 h-3.5" /> Export All
          </a>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">{Array.from({length:6},(_,i)=><div key={i} className="skeleton h-16 w-full rounded-xl" />)}</div>
      ) : sorted.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <Layers className="w-10 h-10 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300">No mailboxes yet.</p>
          <p className="text-xs text-gray-400 mt-1">Import an mbox or Apple Mail archive to populate this view.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {sorted.map((m, i) => (
            <Link key={m.mbox_source} to={`/mailbox/${encodeURIComponent(m.mbox_source)}`}
              className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 hover:border-blue-300 dark:hover:border-blue-700 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}>
                  {(m.mbox_source || '?').charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{m.mbox_source || '(unnamed)'}</div>
                  <div className="text-xs text-gray-400 flex items-center gap-3 mt-0.5">
                    <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{m.count.toLocaleString()}</span>
                    <span className="flex items-center gap-1"><Users className="w-3 h-3" />{m.unique_senders}</span>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{m.first_date?.slice(0,4)}–{m.last_date?.slice(0,4)}</span>
                  </div>
                </div>
              </div>
              {/* Volume bar */}
              <div className="mt-3 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{
                  width: `${(m.count / maxCount) * 100}%`,
                  backgroundColor: COLORS[i % COLORS.length]
                }} />
              </div>
            </Link>
          ))}
        </div>
      )}
      </div>  {/* end mailboxes section */}
    </div>
  )
}

export function MailboxDetail() {
  const { name } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const chart = useChartTheme()

  useEffect(() => {
    setLoading(true)
    api.getMailboxDetail(decodeURIComponent(name))
      .then(setData).catch(console.error).finally(() => setLoading(false))
  }, [name])

  if (loading) return <div className="p-8 text-center text-gray-400">Loading mailbox...</div>
  if (!data || data.error) return (
    <div className="max-w-4xl mx-auto p-12 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
      <Layers className="w-10 h-10 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
      <p className="text-sm font-medium text-gray-600 dark:text-gray-300">{data?.error || 'Mailbox not found'}</p>
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">
        <ArrowLeft className="w-4 h-4" /> Back to mailboxes
      </button>

      {/* Header */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center text-2xl font-bold text-blue-600 dark:text-blue-300">
            <Layers className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{data.name}</h2>
            <div className="text-sm text-gray-500 dark:text-gray-400">{data.first_date?.slice(0,10)} — {data.last_date?.slice(0,10)}</div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 pt-5 border-t border-gray-100 dark:border-gray-800">
          <MS icon={Mail} label="Emails" value={data.total_emails?.toLocaleString()} />
          <MS icon={Users} label="Senders" value={data.unique_senders} />
          <MS icon={Paperclip} label="Attachments" value={data.attachments} />
          <MS icon={MessageSquare} label="Threads" value={data.threads} />
        </div>
      </div>

      {/* Volume timeline */}
      {data.monthly_volume?.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Email Volume Over Time</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.monthly_volume}>
              <CartesianGrid strokeDasharray="3 3" stroke={chart.gridStroke} />
              <XAxis dataKey="month" {...chart.axisProps} tick={{ ...chart.axisProps.tick, fontSize: 9 }} interval="preserveStartEnd"
                tickFormatter={v => { const [y, m] = v.split('-'); return m === '01' ? y : '' }} />
              <YAxis {...chart.axisProps} />
              <Tooltip {...chart.tooltipProps} />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#3b82f6" fillOpacity={chart.dark ? 0.25 : 0.15} strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top senders */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Top Senders</h3>
          <div className="space-y-2">{data.top_senders?.slice(0, 10).map((s, i) => (
            <Link key={s.sender_email} to={`/contact/${encodeURIComponent(s.sender_email)}`}
              className="flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 py-0.5 -mx-1">
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium text-white"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}>
                {(s.sender_name || s.sender_email).charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0 text-sm text-gray-700 dark:text-gray-300 truncate">{s.sender_name || s.sender_email}</div>
              <div className="text-xs text-gray-400 font-medium">{s.count}</div>
            </Link>
          ))}</div>
        </div>

        {/* Yearly breakdown */}
        {data.yearly?.length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Year by Year</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.yearly}>
                <XAxis dataKey="year" {...chart.axisProps} />
                <YAxis {...chart.axisProps} />
                <Tooltip {...chart.tooltipProps} />
                <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Browse emails in this mailbox */}
      <div className="text-center pt-2">
        <Link to={`/emails?mbox_source=${encodeURIComponent(data.name)}`}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <Mail className="w-4 h-4" /> Browse emails in this mailbox
        </Link>
      </div>
    </div>
  )
}

function MS({ icon: Icon, label, value }) {
  return <div className="text-center">
    <Icon className="w-4 h-4 text-gray-400 mx-auto mb-1" />
    <div className="text-lg font-bold text-gray-800 dark:text-gray-200">{value}</div>
    <div className="text-[10px] text-gray-400">{label}</div>
  </div>
}
