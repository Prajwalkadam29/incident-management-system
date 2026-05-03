import { useState, useEffect, useRef } from 'react'

export function useSSE(url) {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('ims_token')

    // SSE doesn't support headers natively — pass token as query param
    const fullUrl = token ? `${url}?token=${token}` : url
    const es = new EventSource(fullUrl)
    esRef.current = es

    es.onopen = () => { setConnected(true); setError(null) }

    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data)
        setData(parsed)
      } catch { /* ignore malformed frames */ }
    }

    es.onerror = () => {
      setConnected(false)
      setError('Connection lost — reconnecting...')
      // Browser auto-reconnects EventSource after 3s
    }

    return () => { es.close(); setConnected(false) }
  }, [url])

  return { data, connected, error }
}