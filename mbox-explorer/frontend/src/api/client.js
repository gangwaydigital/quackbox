/**
 * API client for Mbox Explorer backend.
 *
 * All endpoints are proxied through Vite's dev server
 * so we use relative URLs.
 */

const BASE = '/api'

async function request(path, options = {}) {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `API error: ${res.status}`)
  }
  return res.json()
}

export const api = {
  // -- Stats --
  getStats: () => request('/stats'),

  // -- Emails --
  getEmails: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') query.set(k, v)
    })
    return request(`/emails?${query}`)
  },

  getEmail: (id) => request(`/emails/${id}`),

  searchEmails: (query, page = 1, pageSize = 50) =>
    request(`/emails/search?q=${encodeURIComponent(query)}&page=${page}&page_size=${pageSize}`),

  getSenders: (limit = 100) => request(`/emails/senders?limit=${limit}`),

  getSources: () => request(`/emails/sources`),

  // -- Topics --
  getTopics: () => request('/topics'),

  getTopic: (id, page = 1) => request(`/topics/${id}?page=${page}`),

  generateEmbeddings: (regenerate = false) =>
    request(`/topics/embed?regenerate=${regenerate}`, { method: 'POST' }),

  runClustering: (numClusters = null) =>
    request('/topics/cluster', {
      method: 'POST',
      body: JSON.stringify({
        num_clusters: numClusters,
        regenerate_embeddings: false,
      }),
    }),

  checkOllama: () => request('/topics/status/ollama'),

  // -- Ingest --
  ingestFile: (mboxPath) =>
    request('/ingest', {
      method: 'POST',
      body: JSON.stringify({ mbox_path: mboxPath }),
    }),

  ingestAll: () => request('/ingest/all', { method: 'POST' }),

  listAvailableMbox: () => request('/ingest/sources'),

  // -- Chat --
  chat: (question, conversationHistory = [], model = null) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify({
        question,
        conversation_history: conversationHistory,
        model,
      }),
    }),

  getChatModels: () => request('/chat/models'),

  getArchiveSummary: () => request('/chat/summary'),

  // -- Threads --
  getThreads: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== '') query.set(k, v) })
    return request(`/threads?${query}`)
  },

  getThread: (id) => request(`/threads/${id}`),

  rebuildThreads: () => request('/threads/rebuild', { method: 'POST' }),

  getThreadStatus: () => request('/threads/status'),

  // -- Analytics --
  getVolume: () => request('/analytics/volume'),

  getTopContacts: (limit = 20) => request(`/analytics/contacts?limit=${limit}`),

  getHeatmap: () => request('/analytics/heatmap'),

  getYearly: () => request('/analytics/yearly'),

  getMailboxBreakdown: () => request('/analytics/mailboxes'),

  getThreadStats: () => request('/analytics/threads'),

  getResponseTimes: () => request('/analytics/response-times'),

  computeAnalytics: () => request('/analytics/compute', { method: 'POST' }),
}
