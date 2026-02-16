import { useState, useEffect, createContext, useContext } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Mail, Tags, BarChart3, MessageCircle, MessageSquare, Users, Moon, Sun, Menu, X, Layers, Command, Calendar, Paperclip, Clock, Filter } from 'lucide-react'
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
  const [mobileNav, setMobileNav] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const location = useLocation()

  const loadStats = () => {
    setStatsLoading(true)
    api.getStats().then(s => { setStats(s); setStatsLoading(false) }).catch(() => setStatsLoading(false))
    api.getBadges().then(setBadges).catch(() => {})
  }
  useEffect(() => { loadStats() }, [])
  useEffect(() => { setMobileNav(false) }, [location])
  useKeyboardShortcuts(() => setShowShortcuts(true))

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

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-14 sm:h-16">
              <div className="flex items-center gap-4 sm:gap-5">
                <h1 className="text-lg sm:text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Mail className="w-5 h-5 text-blue-600" />
                  <span className="hidden sm:inline">QuackBox</span>
                  <span className="sm:hidden">QBX</span>
                  {stats?.version && <span className="text-[10px] font-mono font-normal px-1.5 py-0.5 bg-gray-100 text-gray-400 rounded-full hidden sm:inline">v{stats.version}</span>}
                </h1>
                {!needsSetup && (
                  <nav className="hidden xl:flex gap-0.5">
                    {navItems.map(({ path, icon: Icon, label, badge }) => (
                      <Link key={path} to={path} className={`relative flex items-center gap-1 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${location.pathname === path || (path !== '/' && location.pathname.startsWith(path)) ? 'bg-blue-50 text-blue-700' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`}>
                        <Icon className="w-3.5 h-3.5" />{label}
                        {badge && <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-400 rounded-full" />}
                      </Link>
                    ))}
                  </nav>
                )}
              </div>
              <div className="flex items-center gap-2">
                {stats && !needsSetup && (
                  <div className="hidden xl:flex items-center gap-3 text-xs text-gray-500 mr-2">
                    <span>{stats.total_emails?.toLocaleString()} emails</span>
                  </div>
                )}
                {!needsSetup && (
                  <button onClick={() => setShowShortcuts(true)} className="hidden sm:block p-2 rounded-lg hover:bg-gray-100" title="Keyboard shortcuts (?)">
                    <Command className="w-4 h-4 text-gray-400" />
                  </button>
                )}
                <ThemeToggle />
                {!needsSetup && (
                  <button onClick={() => setMobileNav(!mobileNav)} className="xl:hidden p-1.5 rounded-lg hover:bg-gray-100">
                    {mobileNav ? <X className="w-5 h-5 text-gray-600" /> : <Menu className="w-5 h-5 text-gray-600" />}
                  </button>
                )}
              </div>
            </div>
          </div>
          {mobileNav && !needsSetup && (
            <div className="xl:hidden border-t border-gray-200 bg-white px-4 py-2">
              {navItems.map(({ path, icon: Icon, label, badge }) => (
                <Link key={path} to={path} className={`flex items-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium ${location.pathname === path || (path !== '/' && location.pathname.startsWith(path)) ? 'bg-blue-50 text-blue-700' : 'text-gray-600'}`}>
                  <Icon className="w-4 h-4" />{label}
                  {badge && <span className="w-2 h-2 bg-amber-400 rounded-full" />}
                </Link>
              ))}
            </div>
          )}
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
          {needsSetup ? (
            <SetupWizard onComplete={() => { loadStats(); window.location.reload() }} />
          ) : (
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/emails" element={<EmailsPage />} />
              <Route path="/email/:id" element={<EmailDetail />} />
              <Route path="/calendar" element={<CalendarView />} />
              <Route path="/timeline" element={<TimelineView />} />
              <Route path="/threads" element={<ThreadList />} />
              <Route path="/thread/:id" element={<ThreadView />} />
              <Route path="/contacts" element={<ContactList />} />
              <Route path="/contact/:email" element={<ContactProfile />} />
              <Route path="/mailboxes" element={<MailboxList />} />
              <Route path="/mailbox/:name" element={<MailboxDetail />} />
              <Route path="/attachments" element={<AttachmentIndex />} />
              <Route path="/search" element={<AdvancedSearch />} />
            <Route path="/topics" element={<TopicClusters />} />
              <Route path="/chat" element={<Chat />} />
            </Routes>
          )}
        </main>
        {showShortcuts && <ShortcutsHelp onClose={() => setShowShortcuts(false)} />}
      </div>
    </ThemeProvider>
  )
}

function ThemeToggle() {
  const { dark, toggle } = useTheme()
  return (
    <button onClick={toggle} className="p-2 rounded-lg hover:bg-gray-100 transition-colors" title={dark ? 'Light mode' : 'Dark mode'}>
      {dark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-gray-500" />}
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
          setEmails(data.results.map(r => r.email))
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
