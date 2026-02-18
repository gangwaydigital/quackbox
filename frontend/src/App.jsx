import { useState, useEffect, createContext, useContext } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Mail, Tags, BarChart3, MessageCircle, MessageSquare, Users, Moon, Sun, Menu, X, Layers, Command, Calendar, Paperclip, Clock, Filter, ChevronLeft, Settings } from 'lucide-react'
import { api } from './api/client'
import { useKeyboardShortcuts, ShortcutsHelp } from './hooks/useKeyboardShortcuts.jsx'
import SearchBar from './components/SearchBar'
import EmailTable from './components/EmailTable'
import EmailDetail from './components/EmailDetail'
import FilterPanel from './components/FilterPanel'
import TopicClusters from './components/TopicClusters'
import Chat from './components/Chat'
import Dashboard from './components/Dashboard'
import { ThreadList, ThreadView } from './components/Threads'
import { ContactList, ContactProfile } from './components/Contacts'
import { MailboxList, MailboxDetail } from './components/Mailboxes'
import CalendarView from './components/Calendar'
import AttachmentIndex from './components/Attachments'
import TimelineView from './components/Timeline'
import SetupWizard from './components/SetupWizard'
import AdvancedSearch from './components/AdvancedSearch'

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

  const needsSetup = !statsLoading && stats && stats.total_emails === 0

  const navItems = [
    { path: '/', icon: BarChart3, label: 'Dashboard' },
    { path: '/emails', icon: Mail, label: 'Emails' },
    { path: '/search', icon: Filter, label: 'Search' },
    { path: '/calendar', icon: Calendar, label: 'Calendar' },
    { path: '/timeline', icon: Clock, label: 'Timeline' },
    { path: '/threads', icon: MessageSquare, label: 'Threads', badge: badges?.needs_threads },
    { path: '/contacts', icon: Users, label: 'Contacts' },
    { path: '/mailboxes', icon: Layers, label: 'Mailboxes' },
    { path: '/attachments', icon: Paperclip, label: 'Files' },
    { path: '/topics', icon: Tags, label: 'Topics', badge: badges?.needs_topics },
    { path: '/chat', icon: MessageCircle, label: 'Chat' },
  ]

  if (needsSetup) {
    return (
      <ThemeProvider>
        <div className="min-h-screen bg-gray-50">
          <main className="max-w-4xl mx-auto px-4 py-6">
            <SetupWizard onComplete={() => { loadStats(); window.location.reload() }} />
          </main>
        </div>
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gray-50 flex">
        {/* Sidebar */}
        <aside className={`${sidebarOpen ? 'w-52' : 'w-14'} flex-shrink-0 bg-white border-r border-gray-200 sticky top-0 h-screen flex flex-col transition-all duration-200 z-30`}>
          {/* Logo */}
          <Link to="/" className={`flex items-center gap-2 px-3 h-14 border-b border-gray-100 hover:bg-gray-50 transition-colors ${sidebarOpen ? '' : 'justify-center'}`}>
            <span className="text-xl">🦆</span>
            {sidebarOpen && (
              <span className="font-semibold text-gray-900 text-sm">
                QuackBox
                {stats?.version && <span className="text-[9px] font-mono font-normal text-gray-400 ml-1">v{stats.version}</span>}
              </span>
            )}
          </Link>

          {/* Nav items */}
          <nav className="flex-1 overflow-y-auto py-2 px-1.5 space-y-0.5">
            {navItems.map(({ path, icon: Icon, label, badge }) => {
              const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
              return (
                <Link key={path} to={path} title={sidebarOpen ? undefined : label}
                  className={`relative flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${active ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}>
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {sidebarOpen && <span className="truncate">{label}</span>}
                  {badge && <span className={`w-2 h-2 bg-amber-400 rounded-full ${sidebarOpen ? 'ml-auto' : 'absolute top-1 right-1'}`} />}
                </Link>
              )
            })}
          </nav>

          {/* Bottom actions */}
          <div className="border-t border-gray-100 py-2 px-1.5 space-y-0.5">
            {sidebarOpen && stats && (
              <div className="px-2.5 py-1.5 text-[10px] text-gray-400">
                {stats.total_emails?.toLocaleString()} emails
              </div>
            )}
            <button onClick={() => setShowShortcuts(true)} title="Keyboard shortcuts (?)"
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 w-full ${sidebarOpen ? '' : 'justify-center'}`}>
              <Command className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span>Shortcuts</span>}
            </button>
            <ThemeToggleSidebar open={sidebarOpen} />
            <button onClick={() => setSidebarOpen(!sidebarOpen)}
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 w-full ${sidebarOpen ? '' : 'justify-center'}`}>
              <ChevronLeft className={`w-4 h-4 flex-shrink-0 transition-transform ${sidebarOpen ? '' : 'rotate-180'}`} />
              {sidebarOpen && <span>Collapse</span>}
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 overflow-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/emails" element={<EmailsPage />} />
              <Route path="/email/:id" element={<EmailDetail />} />
              <Route path="/calendar" element={<CalendarView />} />
              <Route path="/timeline" element={<TimelineView />} />
              <Route path="/search" element={<AdvancedSearch />} />
              <Route path="/threads" element={<ThreadList />} />
              <Route path="/thread/:id" element={<ThreadView />} />
              <Route path="/contacts" element={<ContactList />} />
              <Route path="/contact/:email" element={<ContactProfile />} />
              <Route path="/mailboxes" element={<MailboxList />} />
              <Route path="/mailbox/:name" element={<MailboxDetail />} />
              <Route path="/attachments" element={<AttachmentIndex />} />
              <Route path="/topics" element={<TopicClusters />} />
              <Route path="/chat" element={<Chat />} />
            </Routes>
          </div>
        </main>

        {showShortcuts && <ShortcutsHelp onClose={() => setShowShortcuts(false)} />}
      </div>
    </ThemeProvider>
  )
}

function ThemeToggleSidebar({ open }) {
  const { dark, toggle } = useTheme()
  return (
    <button onClick={toggle} title={dark ? 'Light mode' : 'Dark mode'}
      className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 w-full ${open ? '' : 'justify-center'}`}>
      {dark ? <Sun className="w-4 h-4 flex-shrink-0 text-amber-400" /> : <Moon className="w-4 h-4 flex-shrink-0" />}
      {open && <span>{dark ? 'Light mode' : 'Dark mode'}</span>}
    </button>
  )
}

function EmailsPage() {
  const [emails, setEmails] = useState([])
  const [filters, setFilters] = useState({})
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState('keyword')
  const [pagination, setPagination] = useState({ page: 1, total: 0, total_pages: 1 })
  const [loading, setLoading] = useState(true)
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
            highlight_body: r.email.highlight_body || null,
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
  return (
    <div className="space-y-4">
      <SearchBar onSearch={(q) => { setSearchQuery(q); setFilters({}) }} onModeChange={setSearchMode} searchMode={searchMode} />
      <div className="flex flex-col md:flex-row gap-4 md:gap-6">
        <FilterPanel onFilter={(f) => { setSearchQuery(''); setFilters(f) }} currentFilters={filters} />
        <div className="flex-1 min-w-0">
          <EmailTable emails={emails} loading={loading} pagination={pagination} onPageChange={(page) => fetchEmails({ page })} searchQuery={searchQuery} />
        </div>
      </div>
    </div>
  )
}
