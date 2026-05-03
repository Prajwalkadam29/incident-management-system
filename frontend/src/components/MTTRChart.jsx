import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import api from '@/api/client'

export function MTTRChart() {
  const [data, setData] = useState([])

  useEffect(() => {
    api.get('/workitems/', { params: { page_size: 100 } })
      .then(res => {
        const closed = res.data.items
          .filter(wi => wi.status === 'CLOSED' && wi.mttr_minutes > 0)
          .map(wi => ({
            date: new Date(wi.closed_at).toLocaleDateString(),
            mttr: Math.round(wi.mttr_minutes),
            component: wi.component_id,
          }))
          .slice(-14) // last 14 closed incidents
        setData(closed)
      })
      .catch(() => {})
  }, [])

  if (data.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-gray-500">
        No closed incidents yet — MTTR chart will appear here
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        MTTR Trend (last {data.length} closed incidents, minutes)
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151' }}
            labelStyle={{ color: '#9ca3af' }}
          />
          <Line type="monotone" dataKey="mttr" stroke="#3b82f6"
                strokeWidth={2} dot={{ fill: '#3b82f6', r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}