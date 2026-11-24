import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Calendar as CalIcon, Mail, ArrowLeft } from 'lucide-react'
import { api } from '../api/client'
import HelpLink from './HelpLink'

const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December']
const DAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

export default function CalendarView() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedDay, setSelectedDay] = useState(null)
  const [dayEmails, setDayEmails] = useState(null)
  const [loadingDay, setLoadingDay] = useState(false)

  useEffect(() => {
    setLoading(true)
    setSelectedDay(null)
    setDayEmails(null)
    api.getCalendarMonth(year, month).then(setData).catch(console.error).finally(() => setLoading(false))
  }, [year, month])

  const handleDayClick = async (dateStr) => {
    setSelectedDay(dateStr)
    setLoadingDay(true)
    try {
      const result = await api.getCalendarDay(dateStr)
      setDayEmails(result)
    } catch (err) { console.error(err) }
    finally { setLoadingDay(false) }
  }

  const prev = () => { if (month === 1) { setYear(y => y - 1); setMonth(12) } else setMonth(m => m - 1) }
  const next = () => { if (month === 12) { setYear(y => y + 1); setMonth(1) } else setMonth(m => m + 1) }

  // Build calendar grid
  const firstDay = new Date(year, month - 1, 1).getDay()
  const daysInMonth = new Date(year, month, 0).getDate()
  const dayMap = {}
  if (data?.days) data.days.forEach(d => { dayMap[d.day] = d })

  const maxCount = data?.days?.length ? Math.max(...data.days.map(d => d.count)) : 1
  const getIntensity = (count) => {
    if (!count) return ''
    const ratio = count / maxCount
    if (ratio < 0.2) return 'bg-blue-100 text-blue-800'
    if (ratio < 0.4) return 'bg-blue-200 text-blue-900'
    if (ratio < 0.6) return 'bg-blue-300 text-blue-900'
    if (ratio < 0.8) return 'bg-blue-400 text-white'
    return 'bg-blue-600 text-white'
  }

  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <CalIcon className="w-5 h-5 text-blue-600" /> Calendar <HelpLink section="calendar" />
        </h2>
        <div className="flex items-center gap-3">
          <button onClick={prev} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><ChevronLeft className="w-4 h-4" /></button>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300 min-w-[140px] text-center">{MONTH_NAMES[month-1]} {year}</span>
          <button onClick={next} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><ChevronRight className="w-4 h-4" /></button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        {/* Day headers */}
        <div className="grid grid-cols-7 gap-1 mb-1">
          {DAY_NAMES.map(d => <div key={d} className="text-center text-[10px] font-medium text-gray-400 py-1">{d}</div>)}
        </div>

        {/* Calendar grid */}
        {loading ? (
          <div className="grid grid-cols-7 gap-1">{Array.from({length:35},(_,i)=><div key={i} className="skeleton aspect-square rounded-lg" />)}</div>
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {cells.map((day, i) => {
              if (day === null) return <div key={`e-${i}`} />
              const dateStr = `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`
              const info = dayMap[dateStr]
              const isSelected = selectedDay === dateStr
              const intensity = getIntensity(info?.count)
              return (
                <button key={day} onClick={() => info && handleDayClick(dateStr)}
                  className={`aspect-square rounded-lg flex flex-col items-center justify-center text-sm transition-all relative
                    ${info ? `cursor-pointer hover:ring-2 hover:ring-blue-400 ${intensity}` : 'text-gray-300'}
                    ${isSelected ? 'ring-2 ring-blue-600 ring-offset-1' : ''}`}>
                  <span className="font-medium">{day}</span>
                  {info && <span className="text-[9px] opacity-80">{info.count}</span>}
                </button>
              )
            })}
          </div>
        )}

        {/* Legend */}
        <div className="flex items-center justify-end gap-1.5 mt-3 text-[10px] text-gray-400">
          <span>Less</span>
          {['bg-gray-100','bg-blue-100','bg-blue-200','bg-blue-300','bg-blue-400','bg-blue-600'].map((c,i) =>
            <div key={i} className={`w-3 h-3 rounded-sm ${c}`} />
          )}
          <span>More</span>
        </div>
      </div>

      {/* Selected day detail */}
      {selectedDay && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
              <Mail className="w-4 h-4" />
              {new Date(selectedDay + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </h3>
            <span className="text-xs text-gray-400">{dayEmails?.total || 0} emails</span>
          </div>
          {loadingDay ? (
            <div className="space-y-2">{Array.from({length:3},(_,i)=><div key={i} className="skeleton h-12 rounded-lg" />)}</div>
          ) : dayEmails?.emails?.length ? (
            <div className="divide-y divide-gray-100 dark:divide-gray-800 max-h-96 overflow-y-auto">
              {dayEmails.emails.map(e => (
                <Link key={e.id} to={`/email/${e.id}`} className="block py-2.5 px-2 -mx-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{e.subject || '(no subject)'}</div>
                      <div className="text-xs text-gray-400">{e.sender_name || e.sender_email} · {e.mbox_source}</div>
                    </div>
                    <div className="text-[10px] text-gray-400 flex-shrink-0">
                      {e.date_sent ? new Date(e.date_sent).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : ''}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : <div className="text-sm text-gray-400 text-center py-4">No emails on this day</div>}
        </div>
      )}
    </div>
  )
}
