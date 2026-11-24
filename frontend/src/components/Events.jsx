import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  CalendarClock, MapPin, Users, RefreshCw, Search, ExternalLink,
  Clock, ChevronLeft, ChevronRight, AlertCircle
} from 'lucide-react'
import { api } from '../api/client'
import HelpLink from './HelpLink'

function formatRange(start, end) {
  if (!start) return ''
  try {
    const s = new Date(start)
    const sStr = s.toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
    if (!end) return sStr
    const e = new Date(end)
    const sameDay = s.toDateString() === e.toDateString()
    const eStr = sameDay
      ? e.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit' })
      : e.toLocaleString(undefined, {
          weekday: 'short', month: 'short', day: 'numeric',
          hour: '2-digit', minute: '2-digit',
        })
    return `${sStr} → ${eStr}`
  } catch { return start }
}

export default function Events() {
  const [data, setData] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [upcomingOnly, setUpcomingOnly] = useState(true)
  const [page, setPage] = useState(1)
  const [indexing, setIndexing] = useState(false)
  const [indexResult, setIndexResult] = useState(null)
  const pollRef = useRef(null)

  const load = async (p = 1) => {
    setLoading(true)
    try {
      const result = await api.getCalendarEvents({
        upcoming: upcomingOnly || undefined,
        search: search || undefined,
        page: p,
      })
      setData(result)
      setPage(p)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      setStats(await api.getCalendarEventStats())
    } catch {}
  }

  useEffect(() => { load(1); loadStats() }, [upcomingOnly])
  useEffect(() => {
    const t = setTimeout(() => load(1), 300)
    return () => clearTimeout(t)
  }, [search])

  // Resume polling on mount if indexing already running
  useEffect(() => {
    api.getCalendarIndexStatus().then(s => {
      if (s.running) startPolling()
    }).catch(() => {})
    return () => stopPolling()
  }, [])

  const startPolling = () => {
    if (pollRef.current) return
    setIndexing(true)
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getCalendarIndexStatus()
        if (!s.running) {
          stopPolling()
          setIndexing(false)
          setIndexResult(s.result || (s.error ? { error: s.error } : null))
          loadStats()
          load(page)
        }
      } catch {}
    }, 2000)
  }

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const triggerIndex = async () => {
    setIndexResult(null)
    try {
      await api.triggerCalendarIndexing()
      startPolling()
    } catch (err) {
      setIndexResult({ error: err.message })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <CalendarClock className="w-5 h-5 text-blue-600 dark:text-blue-400" /> Events
          {stats && (
            <span className="text-sm font-normal text-gray-400">
              ({stats.total_events.toLocaleString()} total · {stats.upcoming_events.toLocaleString()} upcoming)
            </span>
          )}
          <HelpLink section="events" />
        </h2>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search summary / location / organizer…"
              className="pl-8 pr-3 py-1.5 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white rounded-lg w-64 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 gap-0.5">
            <button onClick={() => setUpcomingOnly(true)}
              className={`px-3 py-1.5 text-xs rounded-md font-medium transition-colors ${upcomingOnly ? 'bg-white dark:bg-gray-700 text-gray-800 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-200'}`}>
              Upcoming
            </button>
            <button onClick={() => setUpcomingOnly(false)}
              className={`px-3 py-1.5 text-xs rounded-md font-medium transition-colors ${!upcomingOnly ? 'bg-white dark:bg-gray-700 text-gray-800 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-200'}`}>
              All
            </button>
          </div>
          <button onClick={triggerIndex} disabled={indexing}
            title="Scan all imported emails for calendar events"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            <RefreshCw className={`w-3.5 h-3.5 ${indexing ? 'animate-spin' : ''}`} />
            {indexing ? 'Indexing…' : (stats?.total_events ? 'Re-index' : 'Index events')}
          </button>
        </div>
      </div>

      {indexResult?.error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50 rounded-lg px-4 py-3 flex items-start gap-2 text-sm text-red-700 dark:text-red-300">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-medium">Indexing failed</div>
            <div className="mt-0.5 font-mono text-xs">{indexResult.error}</div>
          </div>
        </div>
      )}
      {indexResult && !indexResult.error && (
        <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700/50 rounded-lg px-4 py-3 text-sm text-green-700 dark:text-green-300">
          Indexed {indexResult.events_indexed} events from {indexResult.emails_with_events} emails
          (scanned {indexResult.scanned}, {indexResult.duration_seconds}s).
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="space-y-2">{Array.from({length: 6}, (_, i) =>
          <div key={i} className="skeleton h-20 rounded-xl" />
        )}</div>
      ) : !data?.items?.length ? (
        <div className="p-12 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <CalendarClock className="w-10 h-10 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
            {stats?.total_events === 0 ? 'No events extracted yet.' : (search ? 'No events match your search.' : 'No events in this view.')}
          </p>
          {stats?.total_events === 0 && (
            <p className="text-xs text-gray-400 mt-1">
              Click <span className="font-medium">Index events</span> to scan your imported emails for meeting invites and `.ics` attachments.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {data.items.map(ev => (
            <EventCard key={ev.id} event={ev} />
          ))}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-2 text-sm text-gray-500 dark:text-gray-400">
              <span>Page {data.page} of {data.total_pages}</span>
              <div className="flex gap-2">
                <button onClick={() => load(page - 1)} disabled={page <= 1}
                  className="flex items-center gap-1 px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <ChevronLeft className="w-3.5 h-3.5" /> Prev
                </button>
                <button onClick={() => load(page + 1)} disabled={page >= data.total_pages}
                  className="flex items-center gap-1 px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  Next <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}


function EventCard({ event }) {
  const isPast = event.start_time && new Date(event.start_time) < new Date()
  const statusColors = {
    CONFIRMED: 'bg-green-50 dark:bg-green-900/40 text-green-700 dark:text-green-300',
    TENTATIVE: 'bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
    CANCELLED: 'bg-red-50 dark:bg-red-900/40 text-red-700 dark:text-red-300',
  }
  const status = (event.status || '').toUpperCase()

  return (
    <div className={`bg-white dark:bg-gray-900 rounded-xl border ${
      isPast ? 'border-gray-200 dark:border-gray-800 opacity-70' : 'border-gray-200 dark:border-gray-700'
    } p-4 space-y-2`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">
              {event.summary || '(untitled event)'}
            </h3>
            {status && statusColors[status] && (
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${statusColors[status]}`}>
                {status}
              </span>
            )}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatRange(event.start_time, event.end_time)}
          </div>
        </div>
        <Link to={`/email/${event.email_id}`}
          title="Open the email this event came from"
          className="text-xs text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 flex items-center gap-1 flex-shrink-0">
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>

      {event.location && (
        <div className="text-xs text-gray-600 dark:text-gray-400 flex items-center gap-1.5">
          <MapPin className="w-3 h-3 text-gray-400 flex-shrink-0" />
          <span className="truncate">{event.location}</span>
        </div>
      )}

      {event.organizer && (
        <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
          <span className="text-gray-400">Organizer:</span> {event.organizer}
        </div>
      )}

      {event.attendees?.length > 0 && (
        <div className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1.5">
          <Users className="w-3 h-3 mt-0.5 text-gray-400 flex-shrink-0" />
          <span className="truncate">
            {event.attendees.length} {event.attendees.length === 1 ? 'attendee' : 'attendees'}
            {event.attendees.length <= 4 && ` — ${event.attendees.join(', ')}`}
          </span>
        </div>
      )}

      {event.description && event.description.length < 280 && (
        <p className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap line-clamp-3 pt-1 border-t border-gray-100 dark:border-gray-800">
          {event.description}
        </p>
      )}
    </div>
  )
}
