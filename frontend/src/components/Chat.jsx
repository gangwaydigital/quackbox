import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { MessageCircle, Send, Bot, User, FileText, Cpu, ChevronDown } from 'lucide-react'
import { api } from '../api/client'
import HelpLink from './HelpLink'

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState(null)
  const [showModelSelect, setShowModelSelect] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const modelDropdownRef = useRef(null)

  useEffect(() => {
    // Load available models
    api.getChatModels().then(data => {
      setModels(data.models || [])
      if (!selectedModel && data.models?.length > 0) {
        // Prefer the backend's configured CHAT_MODEL, fall back to first available
        const preferred = data.models.find(m => m === data.default)
        setSelectedModel(preferred || data.models[0])
      }
    }).catch(() => {})

    // Welcome message
    setMessages([{
      role: 'assistant',
      content: "Hi! I can help you explore your email archive. Ask me anything — who emailed you the most, what topics come up frequently, find specific conversations, or get summaries.\n\nTry something like:\n• \"Who are my top 5 email contacts?\"\n• \"Find emails about project deadlines from 2024\"\n• \"Summarize my conversations with [person]\"\n• \"What topics come up most in my inbox?\"",
      sources: [],
    }])
  }, [])

  // Close model dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target)) {
        setShowModelSelect(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const question = input.trim()
    if (!question || loading) return

    // Add user message
    const userMsg = { role: 'user', content: question }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      // Build conversation history (exclude welcome message and sources)
      const history = messages
        .filter((m, i) => i > 0) // Skip welcome
        .map(m => ({ role: m.role, content: m.content }))

      const data = await api.chat(question, history, selectedModel)

      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || [],
        model: data.model,
        emailsSearched: data.emails_searched,
        error: data.error,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}. Make sure the chat API (Ollama or oMLX) is running with a chat model available.`,
        sources: [],
        error: true,
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const suggestedQuestions = [
    "Who emails me the most?",
    "What are the main topics in my archive?",
    "Find recent emails about invoices",
    "Summarize emails from last year",
  ]

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <MessageCircle className="w-5 h-5 text-blue-600" />
          Chat with your Archive
          <HelpLink section="chat" />
        </h2>

        {/* Model selector */}
        <div className="relative" ref={modelDropdownRef}>
          <button
            onClick={() => setShowModelSelect(!showModelSelect)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <Cpu className="w-3.5 h-3.5" />
            {selectedModel || 'No model'}
            <ChevronDown className="w-3 h-3" />
          </button>
          {showModelSelect && models.length > 0 && (
            <div className="absolute right-0 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 min-w-48">
              {models.map(model => (
                <button
                  key={model}
                  onClick={() => { setSelectedModel(model); setShowModelSelect(false) }}
                  className={`block w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800/50 ${
                    model === selectedModel ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'
                  }`}
                >
                  {model}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-blue-600 dark:text-blue-300" />
              </div>
            )}

            <div className={`max-w-[80%] ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5'
                : 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3'
            }`}>
              {/* Message content */}
              <div className={`text-sm whitespace-pre-wrap leading-relaxed ${
                msg.error ? 'text-red-600' : ''
              }`}>
                {msg.content}
              </div>

              {/* Sources */}
              {msg.sources?.length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-100 dark:border-gray-800">
                  <div className="text-xs text-gray-400 mb-1.5 flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    Sources ({msg.emailsSearched} emails searched)
                  </div>
                  <div className="space-y-1">
                    {msg.sources.slice(0, 5).map((src, j) => (
                      <Link
                        key={j}
                        to={`/email/${src.id}`}
                        className="block text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 truncate"
                      >
                        {src.from}: {src.subject}
                        {src.date && <span className="text-gray-400 ml-1">
                          ({new Date(src.date).toLocaleDateString()})
                        </span>}
                      </Link>
                    ))}
                    {msg.sources.length > 5 && (
                      <span className="text-xs text-gray-400">
                        + {msg.sources.length - 5} more sources
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              </div>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-blue-600 dark:text-blue-300" />
            </div>
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                Searching emails & thinking...
              </div>
            </div>
          </div>
        )}

        {/* Suggested questions (show only at start) */}
        {messages.length <= 1 && (
          <div className="flex flex-wrap gap-2 px-11">
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => { setInput(q); inputRef.current?.focus() }}
                className="px-3 py-1.5 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-full text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 pt-4 pb-2">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your emails..."
            rows={1}
            className="flex-1 resize-none px-4 py-2.5 bg-white dark:bg-gray-800 dark:text-white border border-gray-200 dark:border-gray-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            style={{ minHeight: '44px', maxHeight: '120px' }}
            onInput={(e) => {
              e.target.style.height = '44px'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 text-center">
          Searches your email archive and uses {selectedModel || 'Ollama'} to generate answers
        </p>
      </div>
    </div>
  )
}
