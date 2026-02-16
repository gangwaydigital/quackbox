import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { TrendingUp, TrendingDown, Smile, Frown, Meh, Activity, RefreshCw } from 'lucide-react'
import { api } from '../api/client'

const SENTIMENT_COLORS = {
  'very positive': '#16a34a', positive: '#4ade80', neutral: '#94a3b8',
  negative: '#f87171', 'very negative': '#dc2626'
}

export default function SentimentDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('monthly')

  const load = () => {
    setLoading(true)
    api.getSentiment().then(setData).catch(console.error).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="space-y-4">
      <div className="skeleton h-8 w-64" />
      <div className="grid grid-cols-5 gap-3">{Array.from({length:5},(_,i)=><div key={i} className="skeleton h-24 rounded-xl" />)}</div>
      <div className="skeleton h-64 rounded-xl" />
    </div>
  )
  if (!data) return <div className="p-8 text-center text-gray-400">Could not load sentiment data</div>

  const dist = data.label_distribution || {}
  const total = data.total_analyzed || 1
  const trendData = viewMode === 'monthly' ? data.monthly_trend : data.yearly_trend
  const trendKey = viewMode === 'monthly' ? 'month' : 'year'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-600" /> Sentiment Analysis
          <span className="text-sm font-normal text-gray-400">({total.toLocaleString()} emails analyzed)</span>
        </h2>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 rounded-lg hover:bg-gray-200">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Distribution cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {['very positive','positive','neutral','negative','very negative'].map(label => {
          const count = dist[label] || 0
          const pct = ((count / total) * 100).toFixed(1)
          const icons = { 'very positive': Smile, positive: Smile, neutral: Meh, negative: Frown, 'very negative': Frown }
          const Icon = icons[label]
          return (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <Icon className="w-5 h-5 mx-auto mb-1" style={{ color: SENTIMENT_COLORS[label] }} />
              <div className="text-xl font-bold text-gray-800">{pct}%</div>
              <div className="text-[10px] text-gray-400 capitalize">{label}</div>
              <div className="text-[10px] text-gray-300">{count.toLocaleString()}</div>
            </div>
          )
        })}
      </div>

      {/* Sentiment trend chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-700">Sentiment Over Time</h3>
          <div className="flex gap-1">
            <button onClick={() => setViewMode('monthly')} className={`text-xs px-3 py-1 rounded-full ${viewMode === 'monthly' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>Monthly</button>
            <button onClick={() => setViewMode('yearly')} className={`text-xs px-3 py-1 rounded-full ${viewMode === 'yearly' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>Yearly</button>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={trendData}>
            <defs>
              <linearGradient id="sentPos" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#4ade80" stopOpacity={0.3}/><stop offset="95%" stopColor="#4ade80" stopOpacity={0}/></linearGradient>
              <linearGradient id="sentNeg" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f87171" stopOpacity={0.3}/><stop offset="95%" stopColor="#f87171" stopOpacity={0}/></linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={trendKey} tick={{ fontSize: 10 }} interval="preserveStartEnd"
              tickFormatter={v => viewMode === 'monthly' ? (v.endsWith('-01') ? v.slice(0,4) : '') : v} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
            <Area type="monotone" dataKey="avg_sentiment" stroke="#3b82f6" fill="url(#sentPos)" strokeWidth={1.5} name="Avg Sentiment" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Top senders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-green-500" /> Most Positive Senders
          </h3>
          <div className="space-y-2">{data.most_positive_senders?.slice(0,8).map((s, i) => (
            <Link key={s.email} to={`/contact/${encodeURIComponent(s.email)}`}
              className="flex items-center justify-between hover:bg-gray-50 rounded px-2 py-1 -mx-2">
              <div className="text-sm text-gray-700 truncate flex-1">{s.email}</div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">{s.count} emails</span>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-green-50 text-green-700">+{s.avg_sentiment.toFixed(2)}</span>
              </div>
            </Link>
          ))}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-red-500" /> Most Negative Senders
          </h3>
          <div className="space-y-2">{data.most_negative_senders?.slice(0,8).map((s, i) => (
            <Link key={s.email} to={`/contact/${encodeURIComponent(s.email)}`}
              className="flex items-center justify-between hover:bg-gray-50 rounded px-2 py-1 -mx-2">
              <div className="text-sm text-gray-700 truncate flex-1">{s.email}</div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">{s.count} emails</span>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-red-50 text-red-700">{s.avg_sentiment.toFixed(2)}</span>
              </div>
            </Link>
          ))}</div>
        </div>
      </div>

      {/* Urgency trend */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Urgency Over Time</h3>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data.yearly_trend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="year" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Bar dataKey="urgency" fill="#f59e0b" radius={[3,3,0,0]} name="Urgency Score" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
