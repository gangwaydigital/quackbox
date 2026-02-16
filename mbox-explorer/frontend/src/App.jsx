import { useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Mail, Search, Tags, Upload, BarChart3, MessageCircle, MessageSquare } from 'lucide-react'
import { api } from './api/client'
import SearchBar from './components/SearchBar'
import EmailTable from './components/EmailTable'
import EmailDetail from './components/EmailDetail'
import FilterPanel from './components/FilterPanel'
import TopicClusters from './components/TopicClusters'
import Chat from './components/Chat'
import Dashboard from './components/Dashboard'
import { ThreadList, ThreadView } from './components/Threads'

export default function App() {
  const [stats, setStats] = useState(null)
  const location = useLocation()

  useEffect(() => {
    api.getStats().then(setStats).catch(console.error)
  }, [])

  const navItems = [
    { path: '/', icon: BarChart3, label: 'Dashboard' },
    { path: '/emails', icon: Mail, label: 'Emails' },
    { path: '/threads', icon: MessageSquare, label: 'Threads' },
    { path: '/topics', icon: Tags, label: 'Topics' },
    { path: '/chat', icon: MessageCircle, label: 'Chat' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-6">
              <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                <Mail className="w-5 h-5 text-blue-600" />
                Mbox Explorer
              </h1>
              <nav className="flex gap-1">
                {navItems.map(({ path, icon: Icon, label }) => (
                  <Link
                    key={path}
                    to={path}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      location.pathname === path || (path !== '/' && location.pathname.startsWith(path))
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </Link>
                ))}
              </nav>
            </div>
            {stats && (
              <div className="flex items-center gap-4 text-sm text-gray-500">
                <span className="flex items-center gap-1">
                  <BarChart3 className="w-4 h-4" />
                  {stats.total_emails.toLocaleString()} emails
                </span>
                <span>{stats.unique_senders} senders</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/emails" element={<EmailsPage />} />
          <Route path="/email/:id" element={<EmailDetail />} />
          <Route path="/threads" element={<ThreadList />} />
          <Route path="/thread/:id" element={<ThreadView />} />
          <Route path="/topics" element={<TopicClusters />} />
          <Route path="/chat" element={<Chat />} />
        </Routes>
      </main>
    </div>
  )
}

function EmailsPage() {
  const [emails, setEmails] = useState([])
  const [filters, setFilters] = useState({})
  const [searchQuery, setSearchQuery] = useState('')
  const [pagination, setPagination] = useState({ page: 1, total: 0, total_pages: 1 })
  const [loading, setLoading] = useState(true)

  const fetchEmails = async (params = {}) => {
    setLoading(true)
    try {
      if (searchQuery) {
        const data = await api.searchEmails(searchQuery, params.page || 1)
        setEmails(data.results.map(r => r.email))
        setPagination({ page: data.page, total: data.total, total_pages: Math.ceil(data.total / 50) })
      } else {
        const data = await api.getEmails({ ...filters, ...params })
        setEmails(data.items)
        setPagination({ page: data.page, total: data.total, total_pages: data.total_pages })
      }
    } catch (err) {
      console.error('Failed to fetch emails:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEmails()
  }, [filters, searchQuery])

  const handleSearch = (query) => {
    setSearchQuery(query)
    setFilters({})
  }

  const handleFilter = (newFilters) => {
    setSearchQuery('')
    setFilters(newFilters)
  }

  return (
    <div className="space-y-4">
      <SearchBar onSearch={handleSearch} />
      <div className="flex gap-6">
        <FilterPanel onFilter={handleFilter} currentFilters={filters} />
        <div className="flex-1">
          <EmailTable
            emails={emails}
            loading={loading}
            pagination={pagination}
            onPageChange={(page) => fetchEmails({ page })}
          />
        </div>
      </div>
    </div>
  )
}
