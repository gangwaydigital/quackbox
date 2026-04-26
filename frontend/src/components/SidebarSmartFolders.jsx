/**
 * Sidebar version of saved searches — read-only navigation. Each folder is
 * a Link to /search?saved=<id> that AdvancedSearch picks up and runs.
 *
 * Counts are fetched from /api/saved-searches?with_counts=true and refreshed
 * every minute (and on mount). Cheap because each saved search is one
 * COUNT(*) over the FTS-indexed emails table.
 */
import { useState, useEffect } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { Bookmark } from 'lucide-react'
import { api } from '../api/client'

const REFRESH_INTERVAL_MS = 60_000

function formatCount(n) {
  if (n == null) return '?'
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return n.toLocaleString()
}

export default function SidebarSmartFolders({ open }) {
  const [searches, setSearches] = useState(null)
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const activeId = location.pathname === '/search' ? Number(searchParams.get('saved')) || null : null

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const d = await api.getSavedSearches()
        if (!cancelled) setSearches(d.searches || [])
      } catch {
        if (!cancelled) setSearches([])
      }
    }
    load()
    const id = setInterval(load, REFRESH_INTERVAL_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  if (!searches || searches.length === 0) return null

  return (
    <div className="border-t border-gray-100 dark:border-gray-800 py-2 px-1.5 space-y-0.5">
      {open && (
        <div className="px-2.5 py-1.5 text-[10px] uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Bookmark className="w-2.5 h-2.5" /> Smart Folders
        </div>
      )}
      {searches.map(s => {
        const isActive = activeId === s.id
        return (
          <Link
            key={s.id}
            to={`/search?saved=${s.id}`}
            title={open ? undefined : s.name}
            className={`relative flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${
              isActive
                ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-800 dark:hover:text-gray-200'
            }`}>
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: s.color || '#3b82f6' }} />
            {open && <span className="truncate flex-1">{s.name}</span>}
            {open && s.count != null && (
              <span className={`text-[10px] flex-shrink-0 ${isActive ? 'text-blue-600 dark:text-blue-300' : 'text-gray-400'}`}>
                {formatCount(s.count)}
              </span>
            )}
            {!open && s.count != null && s.count > 0 && (
              <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-current opacity-40" />
            )}
          </Link>
        )
      })}
    </div>
  )
}
