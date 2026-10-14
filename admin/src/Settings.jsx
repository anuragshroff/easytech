import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { State } from './Shared.jsx'

export default function Settings() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api('/superuser/settings')
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const rows = data ? Object.entries(data) : []
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Platform Settings</h1>
      <div className="text-sm text-gray-600">Read-only view of platform configuration</div>
      <State loading={loading} error={error}>
        {data && (
          <div className="rounded-xl border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="px-4 py-2">Key</th>
                  <th className="px-4 py-2">Value</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([k, v]) => (
                  <tr key={k} className="border-b border-gray-100">
                    <td className="px-4 py-2 text-gray-700 font-medium">{k}</td>
                    <td className="px-4 py-2 text-gray-900 break-all">{typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v ?? '-')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </State>
    </div>
  )
}
