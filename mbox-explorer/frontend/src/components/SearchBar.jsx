import { useState, useCallback, useRef } from 'react'
import { Search, X } from 'lucide-react'

export default function SearchBar({ onSearch }) {
  const [value, setValue] = useState('')
  const timerRef = useRef(null)

  const debouncedSearch = useCallback((query) => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      onSearch(query)
    }, 300)
  }, [onSearch])

  const handleChange = (e) => {
    const query = e.target.value
    setValue(query)
    debouncedSearch(query)
  }

  const handleClear = () => {
    setValue('')
    onSearch('')
  }

  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder="Search emails — subjects, senders, body text..."
        className="w-full pl-10 pr-10 py-3 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      {value && (
        <button
          onClick={handleClear}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
