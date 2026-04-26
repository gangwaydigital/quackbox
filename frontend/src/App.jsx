import { useState, useEffect, useRef, createContext, useContext, lazy, Suspense } from 'react'
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Mail, Tags, BarChart3, MessageCircle, MessageSquare, Users, Moon, Sun,
  Menu, X, Layers, Command, Calendar, CalendarClock, Paperclip, Clock, Filter,
  ChevronLeft, Copy
} from 'lucide-react'
import { api } from './api/client'
import { useKeyboardShortcuts, ShortcutsHelp } from './hooks/useKeyboardShortcuts.jsx'

// Eagerly loaded — these render on first paint or are tiny
import SearchBar from './components/SearchBar'
import EmailTable from './components/EmailTable'
import FilterPanel from './components/FilterPanel'
import EmailPane from './components/EmailPane'
import SetupWizard from './components/SetupWizard'
import ImportStatus from './components/ImportStatus'

// Lazy-loaded — each route gets its own JS chunk that only downloads when
// the user navigates to it. Heavy chart-bearing pages (Dashboard, Mailboxes,
// Contacts profile) carry recharts; isolating them keeps initial load small.
const Dashboard      = lazy(() => import('./components/Dashboard'))
const EmailDetail    = lazy(() => import('./components/EmailDetail'))
const TopicClusters  = lazy(() => import('./components/TopicClusters'))
const Chat           = lazy(() => import('./components/Chat'))
const CalendarView   = lazy(() => import('./components/Calendar'))
const AttachmentIndex = lazy(() => import('./components/Attachments'))
const TimelineView   = lazy(() => import('./components/Timeline'))
const AdvancedSearch = lazy(() => import('./components/AdvancedSearch'))
const Deduplication  = lazy(() => import('./components/Deduplication'))
const Events         = lazy(() => import('./components/Events'))
const ThreadList     = lazy(() => import('./components/Threads').then(m => ({ default: m.ThreadList })))
const ThreadView     = lazy(() => import('./components/Threads').then(m => ({ default: m.ThreadView })))
const ContactList    = lazy(() => import('./components/Contacts').then(m => ({ default: m.ContactList })))
const ContactProfile = lazy(() => import('./components/Contacts').then(m => ({ default: m.ContactProfile })))
const MailboxList    = lazy(() => import('./components/Mailboxes').then(m => ({ default: m.MailboxList })))
const MailboxDetail  = lazy(() => import('./components/Mailboxes').then(m => ({ default: m.MailboxDetail })))

const ThemeCtx = createContext()
export const useTheme = () => useContext(ThemeCtx)

function ThemeProvider({ children }) {
  const [dark, setDark] = useState(() => {
    try { return localStorage.getItem('quackbox-theme') === 'dark' } catch { return false }
  })
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('quackbox-theme', dark ? 'dark' : 'light')
  }, [dark])
  return <ThemeCtx.Provider value={{ dark, toggle: () => setDark(d => !d) }}>{children}</ThemeCtx.Provider>
}

export default function App() {
  const [stats, setStats] = useState(null)
  const [badges, setBadges] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try { return localStorage.getItem('quackbox-sidebar') !== 'closed' } catch { return true }
  })
  // Mobile: sidebar drawer open state (separate from desktop collapse)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()

  const loadStats = () => {
    setStatsLoading(true)
    api.getStats().then(s => { setStats(s); setStatsLoading(false) }).catch(() => setStatsLoading(false))
    api.getBadges().then(setBadges).catch(() => {})
  }
  useEffect(() => { loadStats() }, [])
  useKeyboardShortcuts(() => setShowShortcuts(true))

  useEffect(() => {
    localStorage.setItem('quackbox-sidebar', sidebarOpen ? 'open' : 'closed')
  }, [sidebarOpen])

  // Close mobile menu on navigation
  useEffect(() => { setMobileMenuOpen(false) }, [location.pathname])

  const needsSetup = !statsLoading && stats && stats.total_emails === 0

  const navItems = [
    { path: '/', icon: BarChart3, label: 'Dashboard' },
    { path: '/emails', icon: Mail, label: 'Emails' },
    { path: '/search', icon: Filter, label: 'Search' },
    { path: '/calendar', icon: Calendar, label: 'Calendar' },
    { path: '/events', icon: CalendarClock, label: 'Events' },
    { path: '/timeline', icon: Clock, label: 'Timeline' },
    { path: '/threads', icon: MessageSquare, label: 'Threads', badge: badges?.needs_threads },
    { path: '/contacts', icon: Users, label: 'Contacts' },
    { path: '/mailboxes', icon: Layers, label: 'Mailboxes' },
    { path: '/attachments', icon: Paperclip, label: 'Files' },
    { path: '/duplicates', icon: Copy, label: 'Duplicates' },
    { path: '/topics', icon: Tags, label: 'Topics', badge: badges?.needs_topics },
    { path: '/chat', icon: MessageCircle, label: 'Chat' },
  ]

  // Bottom nav items for mobile (show most-used 5)
  const mobileBottomNav = [
    { path: '/', icon: BarChart3, label: 'Home' },
    { path: '/emails', icon: Mail, label: 'Emails' },
    { path: '/search', icon: Filter, label: 'Search' },
    { path: '/threads', icon: MessageSquare, label: 'Threads' },
    { path: '/contacts', icon: Users, label: 'Contacts' },
  ]

  if (needsSetup) {
    return (
      <ThemeProvider>
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
          <main className="max-w-4xl mx-auto px-4 py-6">
            <SetupWizard onComplete={() => { loadStats(); window.location.reload() }} />
          </main>
        </div>
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex">

        {/* ── Desktop Sidebar ──────────────────────────────────────────── */}
        <aside className={`
          hidden md:flex
          ${sidebarOpen ? 'w-52' : 'w-14'}
          flex-shrink-0 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800
          sticky top-0 h-screen flex-col transition-all duration-200 z-30
        `}>
          {/* Logo */}
          <Link to="/"
            className={`flex items-center gap-2 px-3 h-14 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${sidebarOpen ? '' : 'justify-center'}`}>
            <span className="text-xl">🦆</span>
            {sidebarOpen && (
              <span className="font-semibold text-gray-900 dark:text-white text-sm">
                QuackBox
                {stats?.version && (
                  <span className="text-[9px] font-mono font-normal text-gray-400 ml-1">v{stats.version}</span>
                )}
              </span>
            )}
          </Link>

          {/* Nav */}
          <nav className="flex-1 overflow-y-auto py-2 px-1.5 space-y-0.5">
            {navItems.map(({ path, icon: Icon, label, badge }) => {
              const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
              return (
                <Link key={path} to={path} title={sidebarOpen ? undefined : label}
                  className={`relative flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-800 dark:hover:text-gray-200'}`}>
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {sidebarOpen && <span className="truncate">{label}</span>}
                  {badge && (
                    <span className={`w-2 h-2 bg-amber-400 rounded-full ${sidebarOpen ? 'ml-auto' : 'absolute top-1 right-1'}`} />
                  )}
                </Link>
              )
            })}
          </nav>

          {/* Bottom actions */}
          <div className="border-t border-gray-100 dark:border-gray-800 py-2 px-1.5 space-y-0.5">
            {sidebarOpen && stats && (
              <div className="px-2.5 py-1.5 text-[10px] text-gray-400">
                {stats.total_emails?.toLocaleString()} emails
              </div>
            )}
            <button onClick={() => setShowShortcuts(true)} title="Keyboard shortcuts (?)"
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200 w-full ${sidebarOpen ? '' : 'justify-center'}`}>
              <Command className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span>Shortcuts</span>}
            </button>
            <ThemeToggleSidebar open={sidebarOpen} />
            <button onClick={() => setSidebarOpen(!sidebarOpen)}
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200 w-full ${sidebarOpen ? '' : 'justify-center'}`}>
              <ChevronLeft className={`w-4 h-4 flex-shrink-0 transition-transform ${sidebarOpen ? '' : 'rotate-180'}`} />
              {sidebarOpen && <span>Collapse</span>}
            </button>
          </div>
        </aside>

        {/* ── Mobile Header ─────────────────────────────────────────────── */}
        <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 h-14 flex items-center px-4 gap-3">
          <button onClick={() => setMobileMenuOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300 transition-colors">
            <Menu className="w-5 h-5" />
          </button>
          <Link to="/" className="flex items-center gap-2 flex-1">
            <span className="text-lg">🦆</span>
            <span className="font-semibold text-gray-900 dark:text-white text-sm">QuackBox</span>
          </Link>
          <ThemeToggleMobile />
        </div>

        {/* ── Mobile Drawer ─────────────────────────────────────────────── */}
        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/40" onClick={() => setMobileMenuOpen(false)} />
            {/* Drawer */}
            <div className="relative w-64 max-w-[80vw] bg-white dark:bg-gray-900 h-full flex flex-col shadow-2xl">
              <div className="flex items-center justify-between px-4 h-14 border-b border-gray-100 dark:border-gray-800">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🦆</span>
                  <span className="font-semibold text-gray-900 dark:text-white text-sm">QuackBox</span>
                </div>
                <button onClick={() => setMobileMenuOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
                {navItems.map(({ path, icon: Icon, label, badge }) => {
                  const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
                  return (
                    <Link key={path} to={path}
                      className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors ${active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-800 dark:hover:text-gray-200'}`}>
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <span className="flex-1">{label}</span>
                      {badge && <span className="w-2 h-2 bg-amber-400 rounded-full" />}
                    </Link>
                  )
                })}
              </nav>
              {stats && (
                <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-3 text-xs text-gray-400">
                  {stats.total_emails?.toLocaleString()} emails · v{stats.version}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Main Content ───────────────────────────────────────────────── */}
        <main className="flex-1 min-w-0 overflow-auto md:pt-0 pt-14 pb-16 md:pb-0">
          <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-4 sm:py-6">
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/emails" element={<EmailsPage />} />
                <Route path="/email/:id" element={<EmailDetail />} />
                <Route path="/calendar" element={<CalendarView />} />
                <Route path="/events" element={<Events />} />
                <Route path="/timeline" element={<TimelineView />} />
                <Route path="/search" element={<AdvancedSearch />} />
                <Route path="/threads" element={<ThreadList />} />
                <Route path="/thread/:id" element={<ThreadView />} />
                <Route path="/contacts" element={<ContactList />} />
                <Route path="/contact/:email" element={<ContactProfile />} />
                <Route path="/mailboxes" element={<MailboxList />} />
                <Route path="/mailbox/:name" element={<MailboxDetail />} />
                <Route path="/attachments" element={<AttachmentIndex />} />
                <Route path="/duplicates" element={<Deduplication />} />
                <Route path="/topics" element={<TopicClusters />} />
                <Route path="/chat" element={<Chat />} />
              </Routes>
            </Suspense>
          </div>
        </main>

        {/* ── Mobile Bottom Nav ──────────────────────────────────────────── */}
        <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800">
          <nav className="flex items-center justify-around px-2 py-1.5 safe-area-pb">
            {mobileBottomNav.map(({ path, icon: Icon, label }) => {
              const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
              return (
                <Link key={path} to={path}
                  className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-colors min-w-0 ${active ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300'}`}>
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <span className="text-[9px] font-medium truncate">{label}</span>
                </Link>
              )
            })}
            {/* More button → opens drawer */}
            <button onClick={() => setMobileMenuOpen(true)}
              className="flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
              <Menu className="w-5 h-5 flex-shrink-0" />
              <span className="text-[9px] font-medium">More</span>
            </button>
          </nav>
        </div>

        {showShortcuts && <ShortcutsHelp onClose={() => setShowShortcuts(false)} />}
      </div>
    </ThemeProvider>
  )
}

function RouteFallback() {
  return (
    <div className="flex items-center justify-center py-24 text-gray-400">
      <div className="w-5 h-5 border-2 border-gray-200 dark:border-gray-700 border-t-blue-500 rounded-full animate-spin" />
    </div>
  )
}

function ThemeToggleSidebar({ open }) {
  const { dark, toggle } = useTheme()
  return (
    <button onClick={toggle} title={dark ? 'Light mode' : 'Dark mode'}
      className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200 w-full ${open ? '' : 'justify-center'}`}>
      {dark ? <Sun className="w-4 h-4 flex-shrink-0 text-amber-400" /> : <Moon className="w-4 h-4 flex-shrink-0" />}
      {open && <span>{dark ? 'Light mode' : 'Dark mode'}</span>}
    </button>
  )
}

function ThemeToggleMobile() {
  const { dark, toggle } = useTheme()
  return (
    <button onClick={toggle}
      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors">
      {dark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4" />}
    </button>
  )
}

function EmailsPage() {
  const [emails, setEmails]           = useState([])
  const [filters, setFilters]         = useState({})
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode]   = useState('keyword')
  const [pagination, setPagination]   = useState({ page: 1, total: 0, total_pages: 1 })
  const [loading, setLoading]         = useState(true)
  const [selectedId, setSelectedId]   = useState(null)
  const [paneWidth, setPaneWidth]     = useState(42)   // % of container for the reading pane
  const dragging    = useRef(false)
  const containerRef = useRef(null)

  const fetchEmails = async (params = {}) => {
    setLoading(true)
    try {
      if (searchQuery) {
        if (searchMode === 'smart') {
          const data = await api.hybridSearch(searchQuery, 50)
          setEmails(data.results || [])
          setPagination({ page: 1, total: data.total || 0, total_pages: 1 })
        } else {
          const data = await api.searchEmails(searchQuery, params.page || 1)
          setEmails(data.results.map(r => ({
            ...r.email,
            highlight_subject: r.email.highlight_subject || null,
            highlight_body:    r.email.highlight_body    || null,
          })))
          setPagination({ page: data.page, total: data.total, total_pages: Math.ceil(data.total / 50) })
        }
      } else {
        const data = await api.getEmails({ ...filters, ...params })
        setEmails(data.items)
        setPagination({ page: data.page, total: data.total, total_pages: data.total_pages })
      }
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchEmails() }, [filters, searchQuery, searchMode])

  // j/k keyboard navigation
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedId(prev => {
          if (!emails.length) return prev
          const idx = emails.findIndex(em => String(em.id) === String(prev))
          return String(emails[Math.min(idx + 1, emails.length - 1)].id)
        })
      }
      if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedId(prev => {
          if (!emails.length) return prev
          const idx = emails.findIndex(em => String(em.id) === String(prev))
          return String(emails[Math.max(idx - 1, 0)].id)
        })
      }
      if (e.key === 'Escape') setSelectedId(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [emails])

  // Drag divider to resize pane
  const onDividerMouseDown = (e) => {
    e.preventDefault()
    dragging.current = true
    const onMove = (ev) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const raw  = ((ev.clientX - rect.left) / rect.width) * 100
      setPaneWidth(Math.min(Math.max(100 - raw, 25), 70))
    }
    const onUp = () => {
      dragging.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const paneOpen = !!selectedId

  return (
    <div className="space-y-3">
      <SearchBar
        onSearch={(q) => { setSearchQuery(q); setFilters({}); setSelectedId(null) }}
        onModeChange={setSearchMode}
        searchMode={searchMode} />

      <div className="flex flex-col md:flex-row gap-4 md:gap-0" ref={containerRef}>
        {/* Filter sidebar */}
        <div className="md:w-48 lg:w-56 flex-shrink-0 md:pr-4">
          <FilterPanel
            onFilter={(f) => { setSearchQuery(''); setFilters(f); setSelectedId(null) }}
            currentFilters={filters} />
        </div>

        {/* Email list column */}
        <div
          className="flex-1 min-w-0 md:min-w-[260px]"
          style={paneOpen ? { flexBasis: `${100 - paneWidth}%`, flexGrow: 0, flexShrink: 0 } : {}}>
          <EmailTable
            emails={emails}
            loading={loading}
            pagination={pagination}
            onPageChange={(page) => fetchEmails({ page })}
            searchQuery={searchQuery}
            onSelect={(email) => setSelectedId(prev => String(prev) === String(email.id) ? null : String(email.id))}
            selectedId={selectedId} />
          {paneOpen && (
            <p className="mt-2 text-[10px] text-gray-300 text-center hidden md:block select-none">
              j / k to navigate · Esc to close
            </p>
          )}
        </div>

        {/* Drag-to-resize divider */}
        {paneOpen && (
          <div
            onMouseDown={onDividerMouseDown}
            className="hidden md:flex w-2 flex-shrink-0 cursor-col-resize items-center justify-center group select-none">
            <div className="w-0.5 h-12 bg-gray-200 group-hover:bg-blue-400 rounded-full transition-colors" />
          </div>
        )}

        {/* Reading pane — desktop inline */}
        {paneOpen && (
          <div
            className="hidden md:block overflow-y-auto border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950 rounded-xl shadow-sm"
            style={{ flexBasis: `${paneWidth}%`, flexGrow: 0, flexShrink: 0, maxHeight: 'calc(100vh - 130px)' }}>
            <EmailPane emailId={selectedId} onClose={() => setSelectedId(null)} compact />
          </div>
        )}

        {/* Reading pane — mobile full-screen */}
        {paneOpen && (
          <div className="md:hidden fixed inset-0 z-40 bg-white dark:bg-gray-950 overflow-y-auto">
            <EmailPane emailId={selectedId} onClose={() => setSelectedId(null)} />
          </div>
        )}
      </div>
    </div>
  )
}
