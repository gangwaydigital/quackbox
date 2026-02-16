import { useState, useEffect } from 'react'
import { Filter, X } from 'lucide-react'
import { api } from '../api/client'

export default function FilterPanel({ onFilter, currentFilters }) {
  const [senders, setSenders] = useState([])
  const [sources, setSources] = useState([])
  const [expanded, setExpanded] = useState(true)
  const [filters, setFilters] = useState({
    sender_email: '',
    date_from: '',
    date_to: '',
    subject_contains: '',
    mbox_source: '',
    has_attachments: null,
    sort_by: 'date_timestamp',
    sort_order: 'desc',
  })

  useEffect(() => {
    api.getSenders(50).then(data => setSenders(data.senders || [])).catch(() => {})
    api.getSources().then(data => setSources(data.sources || [])).catch(() => {})
  }, [])

  const handleChange = (field, value) => {
    const updated = { ...filters, [field]: value }
    setFilters(updated)
    // Debounce text inputs, immediate for selects
    onFilter(cleanFilters(updated))
  }

  const clearFilters = () => {
    const cleared = {
      sender_email: '',
      date_from: '',
      date_to: '',
      subject_contains: '',
      mbox_source: '',
      has_attachments: null,
      sort_by: 'date_timestamp',
      sort_order: 'desc',
    }
    setFilters(cleared)
    onFilter({})
  }

  const hasActiveFilters = Object.values(filters).some(v => v !== '' && v !== null && v !== 'date_timestamp' && v !== 'desc')

  return (
    <div className="w-64 flex-shrink-0">
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4 sticky top-20">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
            <Filter className="w-4 h-4" />
            Filters
          </h3>
          {hasActiveFilters && (
            <button onClick={clearFilters} className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-0.5">
              <X className="w-3 h-3" /> Clear
            </button>
          )}
        </div>

        {/* Sender filter */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Sender</label>
          <select
            value={filters.sender_email}
            onChange={(e) => handleChange('sender_email', e.target.value)}
            className="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All senders</option>
            {senders.map(s => (
              <option key={s.sender_email} value={s.sender_email}>
                {s.sender_name || s.sender_email} ({s.email_count})
              </option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">From</label>
            <input
              type="date"
              value={filters.date_from}
              onChange={(e) => handleChange('date_from', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">To</label>
            <input
              type="date"
              value={filters.date_to}
              onChange={(e) => handleChange('date_to', e.target.value)}
              className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5"
            />
          </div>
        </div>

        {/* Subject filter */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Subject contains</label>
          <input
            type="text"
            value={filters.subject_contains}
            onChange={(e) => handleChange('subject_contains', e.target.value)}
            placeholder="keyword..."
            className="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5"
          />
        </div>

        {/* Source mbox */}
        {sources.length > 1 && (
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Mbox source</label>
            <select
              value={filters.mbox_source}
              onChange={(e) => handleChange('mbox_source', e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5"
            >
              <option value="">All sources</option>
              {sources.map(s => (
                <option key={s.mbox_source} value={s.mbox_source}>
                  {s.mbox_source} ({s.email_count})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Attachments toggle */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="has_attachments"
            checked={filters.has_attachments === true}
            onChange={(e) => handleChange('has_attachments', e.target.checked ? true : null)}
            className="rounded text-blue-600"
          />
          <label htmlFor="has_attachments" className="text-xs text-gray-600">Has attachments</label>
        </div>

        {/* Sort */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Sort by</label>
          <div className="flex gap-1">
            <select
              value={filters.sort_by}
              onChange={(e) => handleChange('sort_by', e.target.value)}
              className="flex-1 text-xs border border-gray-200 rounded-md px-2 py-1.5"
            >
              <option value="date_timestamp">Date</option>
              <option value="sender_email">Sender</option>
              <option value="subject">Subject</option>
            </select>
            <select
              value={filters.sort_order}
              onChange={(e) => handleChange('sort_order', e.target.value)}
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5"
            >
              <option value="desc">↓ Desc</option>
              <option value="asc">↑ Asc</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}

function cleanFilters(filters) {
  const cleaned = {}
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) cleaned[k] = v
  })
  return cleaned
}
