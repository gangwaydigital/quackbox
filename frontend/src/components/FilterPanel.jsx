import { useState, useEffect } from 'react'
import { Filter, ChevronDown } from 'lucide-react'
import { api } from '../api/client'

export default function FilterPanel({ onFilter, currentFilters }) {
  const [senders, setSenders] = useState([])
  const [sources, setSources] = useState([])
  const [expanded, setExpanded] = useState(false)
  const [filters, setFilters] = useState({
    sender_email: '', date_from: '', date_to: '', mbox_source: '', has_attachments: ''
  })

  useEffect(() => {
    api.getSenders(50).then(d => setSenders(d.senders || [])).catch(() => {})
    api.getSources().then(d => setSources(d.sources || [])).catch(() => {})
  }, [])

  const handleChange = (key, value) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    onFilter(next)
  }

  const clearAll = () => {
    const empty = { sender_email: '', date_from: '', date_to: '', mbox_source: '', has_attachments: '' }
    setFilters(empty)
    onFilter(empty)
  }

  const hasActive = Object.values(filters).some(v => v !== '')

  return (
    <div className="w-full md:w-56 flex-shrink-0">
      {/* Mobile toggle */}
      <button onClick={() => setExpanded(!expanded)} className="md:hidden flex items-center justify-between w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 mb-2">
        <span className="flex items-center gap-1.5"><Filter className="w-4 h-4" />Filters {hasActive && <span className="w-2 h-2 bg-blue-500 rounded-full" />}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      <div className={`${expanded ? 'block' : 'hidden'} md:block space-y-3`}>
        <div className="bg-white rounded-lg border border-gray-200 p-3 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Filters</span>
            {hasActive && <button onClick={clearAll} className="text-xs text-blue-600 hover:text-blue-700">Clear</button>}
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Sender</label>
            <select value={filters.sender_email} onChange={e => handleChange('sender_email', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1.5">
              <option value="">All senders</option>
              {senders.map(s => <option key={s.email} value={s.email}>{s.name || s.email} ({s.count})</option>)}
            </select>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Mailbox</label>
            <select value={filters.mbox_source} onChange={e => handleChange('mbox_source', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1.5">
              <option value="">All mailboxes</option>
              {sources.map(s => <option key={s.source} value={s.source}>{s.source} ({s.count})</option>)}
            </select>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Date from</label>
            <input type="date" value={filters.date_from} onChange={e => handleChange('date_from', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1.5" />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Date to</label>
            <input type="date" value={filters.date_to} onChange={e => handleChange('date_to', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1.5" />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Attachments</label>
            <select value={filters.has_attachments} onChange={e => handleChange('has_attachments', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1.5">
              <option value="">Any</option>
              <option value="true">Has attachments</option>
              <option value="false">No attachments</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}
