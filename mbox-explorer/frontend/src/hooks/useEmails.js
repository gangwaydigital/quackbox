/**
 * Custom hooks for email data management.
 *
 * TODO (Phase 2): Extract data fetching logic from components
 * into reusable hooks for better state management.
 */

import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

/**
 * Hook for fetching paginated email data with filtering.
 *
 * Usage:
 *   const { emails, loading, pagination, setFilters, setPage } = useEmails()
 */
export function useEmails(initialFilters = {}) {
  const [emails, setEmails] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(initialFilters)
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState({ total: 0, total_pages: 1, page: 1 })

  const fetchEmails = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getEmails({ ...filters, page })
      setEmails(data.items)
      setPagination({
        total: data.total,
        total_pages: data.total_pages,
        page: data.page,
      })
    } catch (err) {
      console.error('Failed to fetch emails:', err)
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  useEffect(() => {
    fetchEmails()
  }, [fetchEmails])

  return {
    emails,
    loading,
    pagination,
    filters,
    setFilters: (f) => { setFilters(f); setPage(1) },
    setPage,
    refresh: fetchEmails,
  }
}

/**
 * Hook for full-text search.
 */
export function useSearch() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [pagination, setPagination] = useState({ total: 0, page: 1 })

  const search = useCallback(async (q, page = 1) => {
    if (!q.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    try {
      const data = await api.searchEmails(q, page)
      setResults(data.results)
      setPagination({ total: data.total, page: data.page })
      setQuery(q)
    } catch (err) {
      console.error('Search error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  return { results, loading, query, pagination, search }
}
