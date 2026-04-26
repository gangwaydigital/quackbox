const BASE = '/api'

// Map common HTTP statuses to user-friendly messages. The original API `detail`
// is preserved on `error.detail` for debugging / advanced UIs.
const STATUS_MESSAGES = {
  0:   'Cannot reach the server. Check that the backend is running.',
  400: 'That request was invalid.',
  401: 'You need to sign in to do that.',
  403: 'You do not have permission to do that.',
  404: 'We couldn’t find what you were looking for.',
  408: 'The server took too long to respond. Please try again.',
  409: 'That conflicts with the current state — refresh and retry.',
  413: 'That upload is too large.',
  429: 'Too many requests — slow down a moment and try again.',
  500: 'Something went wrong on the server. Please try again.',
  502: 'The server is unreachable right now. Please try again.',
  503: 'The server is temporarily unavailable. Please try again shortly.',
  504: 'The server timed out. Please try again.',
}

class ApiError extends Error {
  constructor(message, { status = 0, detail = null, path = '' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.path = path
  }
}

function friendlyMessage(status, detail) {
  // Network failures: no useful detail to show, use the mapped message.
  if (status === 0) return STATUS_MESSAGES[0]
  // For HTTP errors, prefer the API's detail if it looks like a real explanation
  // (longer than a bare status word like "Not Found"). The backend writes these
  // intentionally — e.g. "Attachment X not found. The original mbox/emlx source
  // file must be accessible." — and they're more useful than a generic mapping.
  if (typeof detail === 'string') {
    const trimmed = detail.trim()
    if (trimmed.length > 16 && trimmed.length < 240) return trimmed
  }
  return STATUS_MESSAGES[status] || `Something went wrong (status ${status}).`
}

async function request(path, options = {}) {
  const url = `${BASE}${path}`
  let res
  try {
    res = await fetch(url, { headers: { 'Content-Type': 'application/json', ...options.headers }, ...options })
  } catch (networkErr) {
    throw new ApiError(STATUS_MESSAGES[0], { status: 0, detail: String(networkErr), path })
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = body?.detail ?? res.statusText ?? null
    throw new ApiError(friendlyMessage(res.status, detail), { status: res.status, detail, path })
  }
  return res.json()
}

export { ApiError }
export const api = {
  getStats: () => request('/stats'),
  getDashboard: () => request('/analytics/dashboard'),
  getEmails: (params = {}) => { const q = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) }); return request(`/emails?${q}`) },
  getEmail: (id) => request(`/emails/${id}`),
  getEmailClean: (id) => request(`/emails/${id}?clean=true`),
  searchEmails: (q, page = 1, ps = 50) => request(`/emails/search?q=${encodeURIComponent(q)}&page=${page}&page_size=${ps}`),
  instantSearch: (q, limit = 8) => request(`/emails/instant?q=${encodeURIComponent(q)}&limit=${limit}`),
  advancedSearch: (params = {}) => { const q = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) }); return request(`/emails/advanced-search?${q}`) },
  semanticSearch: (q, limit = 20) => request(`/emails/semantic-search?q=${encodeURIComponent(q)}&limit=${limit}`),
  hybridSearch: (q, limit = 20) => request(`/emails/hybrid-search?q=${encodeURIComponent(q)}&limit=${limit}`),
  findSimilar: (id, limit = 10) => request(`/emails/${id}/similar?limit=${limit}`),
  getSenders: (limit = 100) => request(`/emails/senders?limit=${limit}`),
  getSources: () => request(`/emails/sources`),
  getTopics: () => request('/topics'),
  getTopic: (id, page = 1) => request(`/topics/${id}?page=${page}`),
  generateEmbeddings: (r = false) => request(`/topics/embed?regenerate=${r}`, { method: 'POST' }),
  runClustering: (n = null) => request('/topics/cluster', { method: 'POST', body: JSON.stringify({ num_clusters: n, regenerate_embeddings: false }) }),
  checkOllama: () => request('/topics/status/ollama'),
  getClusteringStatus: () => request('/topics/status'),
  cancelClustering: () => request('/topics/cancel', { method: 'POST' }),
  getEmbedModels: () => request('/topics/embed-models'),
  scanData: () => request('/ingest/scan'),
  getWatcherStatus: () => request('/ingest/watcher'),
  triggerWatcherScan: () => request('/ingest/watcher/scan', { method: 'POST' }),
  checkIngest: () => request('/ingest/check'),
  startIngest: (force = false) => request(`/ingest/start?force=${force}`, { method: 'POST' }),
  getIngestProgress: () => request('/ingest/progress'),
  ingestFile: (p) => request('/ingest', { method: 'POST', body: JSON.stringify({ mbox_path: p }) }),
  ingestAll: () => request('/ingest/all', { method: 'POST' }),
  listAvailableMbox: () => request('/ingest/sources'),
  chat: (q, h = [], m = null) => request('/chat', { method: 'POST', body: JSON.stringify({ question: q, conversation_history: h, model: m }) }),
  getChatModels: () => request('/chat/models'),
  getArchiveSummary: () => request('/chat/summary'),
  getThreads: (params = {}) => { const q = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) }); return request(`/threads?${q}`) },
  getThread: (id) => request(`/threads/${id}`),
  rebuildThreads: () => request('/threads/rebuild', { method: 'POST' }),
  getThreadStatus: () => request('/threads/status'),
  summarizeThread: (id, m = null) => request(`/threads/${id}/summarize${m ? '?model=' + m : ''}`, { method: 'POST' }),
  summarizeEmail: (id, m = null) => request(`/threads/email/${id}/summarize${m ? '?model=' + m : ''}`, { method: 'POST' }),
  getVolume: () => request('/analytics/volume'),
  getTopContacts: (l = 20) => request(`/analytics/contacts?limit=${l}`),
  getHeatmap: () => request('/analytics/heatmap'),
  getYearly: () => request('/analytics/yearly'),
  getMailboxBreakdown: () => request('/analytics/mailboxes'),
  getMailboxDetail: (name) => request(`/analytics/mailbox/${encodeURIComponent(name)}`),
  getThreadStats: () => request('/analytics/threads'),
  getResponseTimes: () => request('/analytics/response-times'),
  getNetwork: (min = 1, limit = 80) => request(`/analytics/network?min_shared=${min}&limit=${limit}`),
  getCalendarMonth: (year, month) => request(`/analytics/calendar?year=${year}&month=${month}`),
  getCalendarDay: (date) => request(`/analytics/calendar/day?date=${date}`),
  getTimeline: () => request('/analytics/timeline'),
  getBadges: () => request('/analytics/badges'),
  computeAnalytics: () => request('/analytics/compute', { method: 'POST' }),
  getContacts: (params = {}) => { const q = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) }); return request(`/contacts?${q}`) },
  getContact: (email) => request(`/contacts/${encodeURIComponent(email)}`),
  getMergeCandidates: () => request('/contacts/merge-candidates'),
  mergeContacts: (primary, secondary) => request('/contacts/merge', { method: 'POST', body: JSON.stringify({ primary_email: primary, secondary_emails: secondary }) }),
  getSentiment: () => request('/contacts/sentiment'),
  getAttachments: (params = {}) => { const q = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) }); return request(`/attachments?${q}`) },
  getAttachmentStats: () => request('/attachments/stats'),
  // Attachment downloads & email export
  getEmailAttachments: (id) => request(`/export/email/${id}/attachments`),
  downloadAttachmentUrl: (emailId, filename) => `${BASE}/export/email/${emailId}/attachment/${encodeURIComponent(filename)}`,
  downloadEmlUrl: (emailId) => `${BASE}/export/email/${emailId}/eml`,
  downloadAttachmentsZipUrl: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
    const qs = q.toString()
    return `${BASE}/export/attachments.zip${qs ? `?${qs}` : ''}`
  },
  getSettings: () => request('/settings'),
  // Bookmarks
  getBookmarks: (page = 1) => request(`/bookmarks?page=${page}`),
  addBookmark: (id, note) => request('/bookmarks', { method: 'POST', body: JSON.stringify({ email_id: id, note }) }),
  removeBookmark: (id) => request(`/bookmarks/${id}`, { method: 'DELETE' }),
  checkBookmark: (id) => request(`/bookmarks/check/${id}`),
  // Tags
  getTags: () => request('/bookmarks/tags'),
  createTag: (name, color) => request('/bookmarks/tags', { method: 'POST', body: JSON.stringify({ name, color }) }),
  deleteTag: (id) => request(`/bookmarks/tags/${id}`, { method: 'DELETE' }),
  tagEmails: (tagId, ids) => request(`/bookmarks/tags/${tagId}/emails`, { method: 'POST', body: JSON.stringify({ email_ids: ids }) }),
  untagEmails: (tagId, ids) => request(`/bookmarks/tags/${tagId}/emails`, { method: 'DELETE', body: JSON.stringify({ email_ids: ids }) }),
  getTagEmails: (tagId, page = 1) => request(`/bookmarks/tags/${tagId}/emails?page=${page}`),
  getEmailTags: (id) => request(`/bookmarks/email/${id}/tags`),
  // Deduplication
  scanDuplicates: () => request('/duplicates/scan', { method: 'POST' }),
  getDuplicates: (page = 1, pageSize = 20) => request(`/duplicates?page=${page}&page_size=${pageSize}`),
  deleteDuplicates: (body) => request('/duplicates/delete', { method: 'POST', body: JSON.stringify(body) }),
  dismissDuplicate: (groupId) => request(`/duplicates/${groupId}`, { method: 'DELETE' }),
  // Saved searches
  getSavedSearches: () => request('/saved-searches'),
  createSavedSearch: (body) => request('/saved-searches', { method: 'POST', body: JSON.stringify(body) }),
  deleteSavedSearch: (id) => request(`/saved-searches/${id}`, { method: 'DELETE' }),
  updateSavedSearch: (id, body) => request(`/saved-searches/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  recordSavedSearchRun: (id) => request(`/saved-searches/${id}/run`, { method: 'POST' }),
  // Attachment preview & content search
  getAttachmentPreview: (emailId, filename) => request(`/attachments/${emailId}/${encodeURIComponent(filename)}/preview`),
  searchAttachmentContent: (q, page = 1) => request(`/attachments/search/content?q=${encodeURIComponent(q)}&page=${page}`),
  triggerAttachmentIndexing: () => request('/attachments/index', { method: 'POST' }),
  // Calendar events
  getCalendarEvents: (params = {}) => { const q = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) }); return request(`/calendar-events?${q}`) },
  getCalendarEventStats: () => request('/calendar-events/stats'),
  triggerCalendarIndexing: () => request('/calendar-events/index', { method: 'POST' }),
  getCalendarIndexStatus: () => request('/calendar-events/status'),
}
