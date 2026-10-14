import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { State, fmtDate } from './Shared.jsx'

export default function Usage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api('/superuser/usage')
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Usage</h1>
      <State loading={loading} error={error}>
        {data && (
          <div className="space-y-4">
            <div className="text-sm text-gray-600">Period: {data.period_start} → {data.period_end}</div>
            <div className="rounded-xl border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="px-4 py-2">Org</th>
                    <th className="px-4 py-2">Provider</th>
                    <th className="px-4 py-2">Calls</th>
                    <th className="px-4 py-2">Seconds</th>
                    <th className="px-4 py-2">Minutes</th>
                    <th className="px-4 py-2">Price/s</th>
                    <th className="px-4 py-2">Cost (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.organizations.map((o) => (
                    <tr key={o.organization_id} className="border-b border-gray-100">
                      <td className="px-4 py-2 text-gray-600">{o.organization_id}</td>
                      <td className="px-4 py-2 text-gray-900 truncate max-w-[240px]">{o.provider_id}</td>
                      <td className="px-4 py-2">{o.call_count}</td>
                      <td className="px-4 py-2">{o.total_seconds}</td>
                      <td className="px-4 py-2">{o.total_minutes}</td>
                      <td className="px-4 py-2">{o.price_per_second_usd ?? '-'}</td>
                      <td className="px-4 py-2">{o.cost_usd}</td>
                    </tr>
                  ))}
                  {data.organizations.length === 0 && (
                    <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-500">No completed runs in period</td></tr>
                  )}
                </tbody>
                {data.totals && (
                  <tfoot>
                    <tr className="bg-gray-50">
                      <td className="px-4 py-2 font-medium">Totals</td>
                      <td className="px-4 py-2" />
                      <td className="px-4 py-2 font-medium">{data.totals.call_count}</td>
                      <td className="px-4 py-2 font-medium">{data.totals.total_seconds}</td>
                      <td className="px-4 py-2 font-medium">{data.totals.total_minutes}</td>
                      <td className="px-4 py-2" />
                      <td className="px-4 py-2 font-medium">{data.totals.cost_usd}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        )}
      </State>
    </div>
  )
}
