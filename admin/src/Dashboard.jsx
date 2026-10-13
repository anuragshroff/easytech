import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { State, fmtDate } from './Shared.jsx'

function Kpi({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-3xl font-semibold text-gray-900">{value}</div>
    </div>
  )
}

function Impersonate() {
  const [providerUserId, setProviderUserId] = useState('')
  const [userId, setUserId] = useState('')
  const [email, setEmail] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const data = await api('/superuser/impersonate', {
        method: 'POST',
        body: JSON.stringify({
          provider_user_id: providerUserId || null,
          user_id: userId ? Number(userId) : null,
          email: email || null,
        }),
      })
      setResult(data.access_token ? 'Impersonation tokens issued.' : JSON.stringify(data))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h2 className="text-lg font-medium text-gray-900">Impersonate user</h2>
      <form onSubmit={onSubmit} className="mt-3 space-y-3">
        <input
          value={providerUserId}
          onChange={(e) => setProviderUserId(e.target.value)}
          placeholder="Provider user ID"
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
        />
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="User ID (integer)"
          type="number"
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
        />
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          type="email"
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? 'Impersonating...' : 'Impersonate'}
        </button>
      </form>
      {result && <p className="mt-3 text-sm text-emerald-600">{result}</p>}
      {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [runs, setRuns] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api('/superuser/stats'), api('/superuser/workflow-runs?page=1&limit=10')])
      .then(([s, r]) => {
        setStats(s)
        setRuns(r.workflow_runs)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <State loading={loading} error={error}>
        {stats && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            <Kpi label="Users" value={stats.total_users} />
            <Kpi label="Organizations" value={stats.total_organizations} />
            <Kpi label="Total runs" value={stats.total_runs} />
            <Kpi label="Completed" value={stats.completed_runs} />
            <Kpi label="Active" value={stats.active_runs} />
            <Kpi label="Runs today" value={stats.runs_today} />
          </div>
        )}
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-medium text-gray-900">Recent runs</h2>
            {!stats && runs === null ? null : (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="pb-2">Name</th>
                    <th className="pb-2">Mode</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {(runs || []).map((r) => (
                    <tr key={r.id} className="border-b border-gray-100">
                      <td className="py-2 font-medium text-gray-900">{r.name || `Run ${r.id}`}</td>
                      <td className="py-2 text-gray-600">{r.mode}</td>
                      <td className="py-2">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            r.is_completed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                          }`}
                        >
                          {r.is_completed ? 'Completed' : 'Active'}
                        </span>
                      </td>
                      <td className="py-2 text-gray-600">{fmtDate(r.created_at)}</td>
                    </tr>
                  ))}
                  {runs && runs.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-4 text-center text-gray-500">
                        No runs yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
          <Impersonate />
        </div>
      </State>
    </div>
  )
}