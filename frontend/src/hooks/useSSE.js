import { useState, useEffect, useRef } from 'react'

export function useSSE(url) {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const esRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(1000) // Start with 1s delay

  useEffect(() => {
    let active = true

    function connect() {
      if (!active) return

      const token = localStorage.getItem('ims_token')
      const fullUrl = token ? `${url}?token=${token}` : url

      if (esRef.current) {
        esRef.current.close()
      }

      const es = new EventSource(fullUrl)
      esRef.current = es

      es.onopen = () => {
        if (!active) return
        setConnected(true)
        setError(null)
        reconnectDelayRef.current = 1000 // Reset backoff delay on successful connection
      }

      es.onmessage = (e) => {
        if (!active) return
        try {
          const parsed = JSON.parse(e.data)
          setData(parsed)
        } catch { /* ignore malformed frames */ }
      }

      // Handle server-side forced JWT expiration
      es.addEventListener('auth_error', (e) => {
        if (!active) return
        setConnected(false)
        setError('Session expired. Please log in again.')
        es.close()
        // Dispatch custom event to let the root auth provider know session expired
        window.dispatchEvent(new CustomEvent('ims_auth_expired'))
      })

      es.onerror = () => {
        if (!active) return
        setConnected(false)
        es.close()

        const delay = reconnectDelayRef.current
        setError(`Connection lost — reconnecting in ${(delay / 1000).toFixed(0)}s...`)
        
        // Exponential backoff capped at 30s
        reconnectDelayRef.current = Math.min(delay * 2, 30000)

        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }

    connect()

    return () => {
      active = false
      if (esRef.current) {
        esRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [url])

  return { data, connected, error }
}