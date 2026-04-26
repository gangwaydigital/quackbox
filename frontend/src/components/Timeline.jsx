import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Clock, Rocket, Mail, Zap, UserPlus, MessageSquare, TrendingUp, TrendingDown, Award, Filter } from 'lucide-react'
import { api } from '../api/client'

const ICONS = {
  rocket: Rocket, mail: Mail, zap: Zap, 'user-plus': UserPlus,
  'message-square': MessageSquare, 'trending-up': TrendingUp,
  'trending-down': TrendingDown, award: Award,
}
const TYPE_COLORS = {
  first_email: '#3b82f6', last_email: '#3b82f6', busy_day: '#f59e0b',
  first_contact: '#8b5cf6', big_thread: '#ec4899', volume_jump: '#10b981',
  volume_drop: '#ef4444', count_milestone: '#6366f1',
}
const TYPE_LABELS = {
  first_email: 'First Email', last_email: 'Latest', busy_day: 'Busiest Days',
  first_contact: 'First Contact', big_thread: 'Big Threads',
  volume_jump: 'Volume Surge', volume_drop: 'Volume Drop',
  count_milestone: 'Milestone',
}

export default function TimelineView() {
  const [milestones, setMilestones] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    setLoading(true)
    api.getTimeline().then(d => setMilestones(d.milestones || []))
      .catch(console.error).finally(() => setLoading(false))
  }, [])

  const types = milestones ? [...new Set(milestones.map(m => m.type))] : []
  const filtered = milestones && filter !== 'all'
    ? milestones.filter(m => m.type === filter) : milestones

  if (loading) return (
    <div className="space-y-4">
      <div className="skeleton h-8 w-48" />
      {Array.from({length: 6}, (_, i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Clock className="w-5 h-5 text-blue-600" /> Email Timeline
          {milestones && <span className="text-sm font-normal text-gray-400">({filtered.length} milestones)</span>}
        </h2>
        <div className="flex flex-wrap gap-1">
          <button onClick={() => setFilter('all')}
            className={`text-xs px-2.5 py-1 rounded-full transition-colors ${filter === 'all' ? 'bg-gray-900 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-500 hover:bg-gray-200'}`}>
            All
          </button>
          {types.map(t => (
            <button key={t} onClick={() => setFilter(t)}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${filter === t ? 'text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-500 hover:bg-gray-200'}`}
              style={filter === t ? { backgroundColor: TYPE_COLORS[t] } : {}}>
              {TYPE_LABELS[t] || t}
            </button>
          ))}
        </div>
      </div>

      {!filtered?.length ? (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center text-gray-400">No milestones found</div>
      ) : (
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" style={{ marginLeft: '11px' }} />

          <div className="space-y-1">
            {filtered.map((m, i) => {
              const Icon = ICONS[m.icon] || Clock
              const color = TYPE_COLORS[m.type] || '#6b7280'
              const date = m.date ? new Date(m.date) : null
              const prevDate = i > 0 && filtered[i-1].date ? new Date(filtered[i-1].date) : null
              const showYear = date && (!prevDate || date.getFullYear() !== prevDate.getFullYear())

              return (
                <div key={`${m.type}-${i}`}>
                  {showYear && (
                    <div className="flex items-center gap-3 py-3 ml-3">
                      <div className="w-5 h-5 rounded-full bg-gray-900 flex items-center justify-center z-10">
                        <span className="text-[8px] text-white font-bold">{date.getFullYear().toString().slice(2)}</span>
                      </div>
                      <span className="text-sm font-bold text-gray-900 dark:text-white">{date.getFullYear()}</span>
                    </div>
                  )}
                  <div className="flex items-start gap-3 py-2 ml-3 group">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center z-10 flex-shrink-0 mt-1"
                      style={{ backgroundColor: color + '20', border: `2px solid ${color}` }}>
                      <Icon className="w-2.5 h-2.5" style={{ color }} />
                    </div>
                    <div className="flex-1 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 group-hover:border-gray-300 dark:group-hover:border-gray-600 transition-colors min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-gray-800 dark:text-gray-200">{m.title}</div>
                          <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">{m.description}</div>
                        </div>
                        <div className="text-[10px] text-gray-400 flex-shrink-0 whitespace-nowrap">
                          {date ? date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
                        </div>
                      </div>
                      <div className="flex gap-2 mt-2">
                        {m.email_id && (
                          <Link to={`/email/${m.email_id}`} className="text-[10px] px-2 py-0.5 bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 rounded hover:bg-blue-100">
                            View email
                          </Link>
                        )}
                        {m.thread_id && (
                          <Link to={`/thread/${m.thread_id}`} className="text-[10px] px-2 py-0.5 bg-pink-50 dark:bg-pink-900/40 text-pink-600 dark:text-pink-300 rounded hover:bg-pink-100">
                            View thread
                          </Link>
                        )}
                        {m.contact && (
                          <Link to={`/contact/${encodeURIComponent(m.contact)}`} className="text-[10px] px-2 py-0.5 bg-purple-50 dark:bg-purple-900/40 text-purple-600 dark:text-purple-300 rounded hover:bg-purple-100">
                            View profile
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
