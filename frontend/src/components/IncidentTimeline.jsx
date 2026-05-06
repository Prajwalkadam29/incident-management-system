import { useEffect, useState } from 'react'
import api from '@/api/client'

const EVENT_CONFIG = {
  INCIDENT_CREATED:   { icon: '🔴', color: 'border-red-500',    label: 'Incident Created'   },
  STATUS_CHANGED:     { icon: '🔄', color: 'border-blue-500',   label: 'Status Changed'     },
  SIGNAL_RECEIVED:    { icon: '📡', color: 'border-yellow-500', label: 'Signal Received'    },
  RCA_SUBMITTED:      { icon: '📋', color: 'border-green-500',  label: 'RCA Submitted'      },
  INCIDENT_CLOSED:    { icon: '🔒', color: 'border-green-500',  label: 'Incident Closed'    },
  ALERT_FIRED:        { icon: '🚨', color: 'border-red-500',    label: 'Alert Fired'        },
  CORRELATION_LINKED: { icon: '🔗', color: 'border-purple-500', label: 'Correlation Linked' },
  COMMENT_ADDED:      { icon: '💬', color: 'border-gray-500',   label: 'Comment Added'      },
}

export function IncidentTimeline({ workItemId }) {
  const [events,  setEvents]  = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/workitems/${workItemId}/timeline`)
      .then(res => setEvents(res.data.events || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [workItemId])

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <p className="text-gray-600 text-sm animate-pulse">Loading timeline...</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold text-white flex items-center gap-2">
          📅 Incident Timeline
          <span className="text-gray-500 font-normal text-sm">({events.length} events)</span>
        </h2>
      </div>

      {/* Timeline */}
      <div className="p-6">
        {events.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-4">
            No events recorded yet
          </p>
        ) : (
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-800" />

            <div className="space-y-4">
              {events.map((event, idx) => {
                const config = EVENT_CONFIG[event.event_type] || {
                  icon: '⚪', color: 'border-gray-500', label: event.event_type
                }

                return (
                  <div key={event.id} className="relative flex gap-4">
                    {/* Dot */}
                    <div className={`relative z-10 w-8 h-8 rounded-full bg-gray-900 border-2 ${config.color} flex items-center justify-center text-sm shrink-0`}>
                      {config.icon}
                    </div>

                    {/* Content */}
                    <div className="flex-1 pb-2">
                      <div className="flex items-start justify-between gap-2 flex-wrap">
                        <div>
                          <span className="text-sm text-white font-medium">
                            {event.summary}
                          </span>
                          {event.actor && event.actor !== 'system' && (
                            <span className="ml-2 text-xs text-blue-400">
                              by {event.actor}
                            </span>
                          )}
                          {event.actor === 'system' && (
                            <span className="ml-2 text-xs text-gray-600">
                              system
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-gray-600 whitespace-nowrap shrink-0">
                          {new Date(event.created_at).toLocaleTimeString()}
                        </span>
                      </div>

                      {/* Metadata pills */}
                      {event.metadata && Object.keys(event.metadata).length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {Object.entries(event.metadata)
                            .filter(([k, v]) => v !== null && v !== undefined)
                            .slice(0, 3)
                            .map(([key, value]) => (
                              <span key={key}
                                className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-mono">
                                {key}: {String(value)}
                              </span>
                            ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}

              {/* End dot */}
              <div className="relative flex gap-4">
                <div className="relative z-10 w-8 h-8 rounded-full bg-gray-900 border-2 border-gray-700 flex items-center justify-center text-sm shrink-0">
                  ⬤
                </div>
                <div className="flex-1 pt-1">
                  <span className="text-xs text-gray-600">
                    {events.length} event{events.length !== 1 ? 's' : ''} recorded
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}