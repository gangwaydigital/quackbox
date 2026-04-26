import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Users, ArrowLeft, Search, Mail, Clock, MessageSquare, Download, Activity, GitMerge } from 'lucide-react'
import { api } from '../api/client'
import { useChartTheme } from '../hooks/useChartTheme'
import SentimentDashboard from './Sentiment'
import ContactMerge from './ContactMerge'

const COLORS = ['#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981','#6366f1']

export function ContactList() {
  const [contacts, setContacts] = useState([])
  const [pagination, setPagination] = useState({ page:1, total:0, total_pages:1 })
  const [sortBy, setSortBy] = useState('total')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [subTab, setSubTab] = useState('directory')

  const load = async (page = 1) => {
    setLoading(true)
    try {
      const data = await api.getContacts({ page, sort_by: sortBy, page_size: 50, search: search || undefined })
      setContacts(data.items)
      setPagination({ page: data.page, total: data.total, total_pages: data.total_pages })
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  useEffect(() => { if (subTab === 'directory') load() }, [sortBy, subTab])
  useEffect(() => { if (subTab === 'directory') { const t = setTimeout(() => load(), 300); return () => clearTimeout(t) } }, [search])

  const subTabs = [
    { id: 'directory', icon: Users, label: 'Directory' },
    { id: 'sentiment', icon: Activity, label: 'Sentiment' },
    { id: 'merge', icon: GitMerge, label: 'Merge' },
  ]

  return (
    <div className="space-y-4">
      {/* Sub-navigation */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          {subTabs.map(({ id, icon: Icon, label }) => (
            <button key={id} onClick={() => setSubTab(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                subTab === id
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}>
              <Icon className="w-3.5 h-3.5" />{label}
            </button>
          ))}
        </div>
        {subTab === 'directory' && (
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search contacts..."
                className="pl-8 pr-3 py-1.5 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white rounded-lg w-48 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white rounded-lg px-2 py-1.5">
              <option value="total">Most Emails</option>
              <option value="last">Most Recent</option>
              <option value="name">Name A-Z</option>
              <option value="first">Earliest Contact</option>
            </select>
            <a href="/api/export/contacts" download
              className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700">
              <Download className="w-3.5 h-3.5" /> CSV
            </a>
          </div>
        )}
      </div>

      {/* Conditional content based on sub-tab */}
      {subTab === 'sentiment' && <SentimentDashboard />}
      {subTab === 'merge' && <ContactMerge />}
      {subTab === 'directory' && (
        <>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <div className="p-4 space-y-2">{Array.from({length:8},(_,i)=><div key={i} className="skeleton h-14 rounded-lg" />)}</div>
            ) : contacts.length === 0 ? (
              <div className="p-12 text-center">
                <Users className="w-10 h-10 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
                <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
                  {search ? 'No contacts match your search.' : 'No contacts yet.'}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {search ? 'Try a different name or email.' : 'Import an mbox archive to populate your directory.'}
                </p>
              </div>
            ) : contacts.map((c, i) => (
              <Link key={c.sender_email} to={`/contact/${encodeURIComponent(c.sender_email)}`}
                className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                <div className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium text-white flex-shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}>
                  {(c.display_name || c.sender_email).charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{c.display_name || c.sender_email}</div>
                  <div className="text-xs text-gray-400 truncate">{c.sender_email}</div>
                </div>
                <div className="text-right flex-shrink-0 space-y-0.5">
                  <div className="text-sm font-semibold text-gray-600 dark:text-gray-300">{c.total_emails.toLocaleString()}</div>
                  <div className="text-[10px] text-gray-400 flex items-center gap-2 justify-end">
                    {c.thread_count > 0 && <span className="flex items-center gap-0.5"><MessageSquare className="w-2.5 h-2.5" />{c.thread_count}</span>}
                    <span>{c.mailbox_count} mailbox{c.mailbox_count !== 1 ? 'es' : ''}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
          {pagination.total_pages > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>Page {pagination.page} of {pagination.total_pages}</span>
              <div className="flex gap-2">
                <button onClick={() => load(pagination.page - 1)} disabled={pagination.page <= 1}
                  className="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800">Prev</button>
                <button onClick={() => load(pagination.page + 1)} disabled={pagination.page >= pagination.total_pages}
                  className="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800">Next</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export function ContactProfile() {
  const { email } = useParams()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const chart = useChartTheme()

  useEffect(() => {
    setLoading(true)
    api.getContact(decodeURIComponent(email))
      .then(setProfile).catch(console.error).finally(() => setLoading(false))
  }, [email])

  if (loading) return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="skeleton h-6 w-32" />
      <div className="skeleton h-48 rounded-xl" />
      <div className="skeleton h-48 rounded-xl" />
    </div>
  )
  if (!profile) return (
    <div className="max-w-4xl mx-auto p-12 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
      <Users className="w-10 h-10 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
      <p className="text-sm font-medium text-gray-600 dark:text-gray-300">Contact not found</p>
      <p className="text-xs text-gray-400 mt-1">The address may have been merged or deleted.</p>
    </div>
  )

  const rs = profile.relationship_score || {}

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center text-2xl font-bold text-blue-600 dark:text-blue-300">
            {(profile.sender_name || profile.sender_email).charAt(0).toUpperCase()}
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{profile.sender_name || profile.sender_email}</h2>
            <div className="text-sm text-gray-500 dark:text-gray-400">{profile.sender_email}</div>
            {profile.known_names?.length > 1 && (
              <div className="text-xs text-gray-400 mt-1">Also known as: {profile.known_names.join(', ')}</div>
            )}
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">{rs.score || 0}</div>
            <div className="text-xs text-gray-400">{rs.label || 'unknown'}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 pt-5 border-t border-gray-100 dark:border-gray-800">
          <MS icon={Mail} label="Total Emails" value={profile.total_emails?.toLocaleString()} />
          <MS icon={MessageSquare} label="Threads" value={profile.thread_count} />
          <MS icon={Clock} label="First Contact" value={profile.first_seen ? new Date(profile.first_seen).toLocaleDateString() : '—'} />
          <MS icon={Clock} label="Last Contact" value={profile.last_seen ? new Date(profile.last_seen).toLocaleDateString() : '—'} />
        </div>

        {rs.breakdown && (
          <div className="flex gap-2 mt-4">
            {Object.entries(rs.breakdown).map(([key, val]) => (
              <div key={key} className="flex-1 bg-gray-50 dark:bg-gray-800 rounded-lg p-2 text-center">
                <div className="text-lg font-bold text-gray-700 dark:text-gray-200">{val}</div>
                <div className="text-[10px] text-gray-400 capitalize">{key}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {profile.monthly_volume?.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Communication Over Time</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={profile.monthly_volume}>
              <XAxis dataKey="month" {...chart.axisProps} tick={{ ...chart.axisProps.tick, fontSize: 9 }} interval="preserveStartEnd"
                tickFormatter={v => { const [y, m] = v.split('-'); return m === '01' ? y : '' }} />
              <YAxis {...chart.axisProps} />
              <Tooltip {...chart.tooltipProps}
                labelFormatter={v => { const [y, m] = v.split('-'); return new Date(y, m - 1).toLocaleString('default', { month: 'long', year: 'numeric' }) }} />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#3b82f6" fillOpacity={chart.dark ? 0.25 : 0.15} strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">When They Email</h3>
          {profile.peak_hours?.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-gray-400 mb-1">Peak Hours</div>
              <div className="flex gap-2">{profile.peak_hours.map((h, i) => (
                <span key={i} className="px-2.5 py-1 bg-blue-50 dark:bg-blue-900/40 rounded text-sm text-blue-700 dark:text-blue-300 font-medium">{h.hour}:00 <span className="text-xs text-blue-400">({h.count})</span></span>
              ))}</div>
            </div>
          )}
          {profile.peak_days?.length > 0 && (
            <div>
              <div className="text-xs text-gray-400 mb-1">Peak Days</div>
              <div className="flex gap-2">{profile.peak_days.map((d, i) => (
                <span key={i} className="px-2.5 py-1 bg-purple-50 dark:bg-purple-900/40 rounded text-sm text-purple-700 dark:text-purple-300 font-medium">{d.day} <span className="text-xs text-purple-400">({d.count})</span></span>
              ))}</div>
            </div>
          )}
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Mailboxes</h3>
          <div className="space-y-1.5">{profile.mailboxes?.map((m, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="text-gray-700 dark:text-gray-300">{m.name}</span>
              <span className="text-gray-400 font-medium">{m.count}</span>
            </div>
          ))}</div>
        </div>
      </div>

      {profile.top_subjects?.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Most Common Subjects</h3>
          <div className="space-y-1.5">{profile.top_subjects.slice(0, 8).map((s, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="w-6 text-right text-xs text-gray-400">{s.count}</span>
              <span className="text-gray-700 dark:text-gray-300 truncate">{s.subject}</span>
            </div>
          ))}</div>
        </div>
      )}

      {profile.recent_emails?.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Recent Emails</h3>
          <div className="divide-y divide-gray-100 dark:divide-gray-800">{profile.recent_emails.map(e => (
            <Link key={e.id} to={`/email/${e.id}`} className="block py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-2 -mx-2">
              <div className="text-sm text-gray-800 dark:text-gray-200 truncate">{e.subject || '(no subject)'}</div>
              <div className="text-xs text-gray-400">{e.date_sent ? new Date(e.date_sent).toLocaleDateString() : ''} · {e.mbox_source}</div>
            </Link>
          ))}</div>
        </div>
      )}
    </div>
  )
}

function MS({ icon: Icon, label, value }) {
  return <div className="text-center">
    <Icon className="w-4 h-4 text-gray-400 mx-auto mb-1" />
    <div className="text-lg font-bold text-gray-800">{value}</div>
    <div className="text-[10px] text-gray-400">{label}</div>
  </div>
}
