import { useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

const SHORTCUTS = {
  '/': 'Focus search bar',
  'Escape': 'Go back / close',
  'g d': 'Go to Dashboard',
  'g e': 'Go to Emails',
  'g t': 'Go to Threads',
  'g c': 'Go to Contacts',
  'g p': 'Go to Topics',
  'g h': 'Go to Chat',
  'g l': 'Go to Timeline',
  'g s': 'Go to Search',
  'g m': 'Go to Mailboxes',
  '?': 'Show shortcuts help',
}

export function useKeyboardShortcuts(onShowHelp) {
  const navigate = useNavigate()
  const location = useLocation()

  const handler = useCallback((e) => {
    const tag = e.target.tagName
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable

    // / to focus search (only if not in input)
    if (e.key === '/' && !isInput) {
      e.preventDefault()
      const searchInput = document.querySelector('input[type="text"][placeholder*="earch"]')
      if (searchInput) searchInput.focus()
      return
    }

    // Escape — blur input or go back
    if (e.key === 'Escape') {
      if (isInput) {
        e.target.blur()
        return
      }
      window.history.back()
      return
    }

    // ? for help
    if (e.key === '?' && !isInput) {
      e.preventDefault()
      if (onShowHelp) onShowHelp()
      return
    }

    // g + letter combos (use a buffer)
    if (!isInput && e.key === 'g') {
      window._gPressed = true
      setTimeout(() => { window._gPressed = false }, 800)
      return
    }

    if (!isInput && window._gPressed) {
      window._gPressed = false
      const routes = { d: '/', e: '/emails', t: '/threads', c: '/contacts', p: '/topics', h: '/chat', m: '/mailboxes', l: '/timeline', s: '/search' }
      if (routes[e.key]) {
        e.preventDefault()
        navigate(routes[e.key])
      }
      return
    }
  }, [navigate, onShowHelp])

  useEffect(() => {
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handler])

  return SHORTCUTS
}

export function ShortcutsHelp({ onClose }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-xl border border-gray-200 p-6 max-w-sm w-full mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Keyboard Shortcuts</h3>
        <div className="space-y-2">
          {Object.entries(SHORTCUTS).map(([key, desc]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-gray-600">{desc}</span>
              <kbd className="px-2 py-0.5 bg-gray-100 rounded text-xs font-mono text-gray-700 border border-gray-200">{key}</kbd>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs text-gray-400 text-center">Press Esc to close</div>
      </div>
    </div>
  )
}
