import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import Pager, { State, fmtDate } from './Shared.jsx'

export default function Runs() {
  const [page, setPage] = useState(1)
  const [limit] = useState(50)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api(`/superuser/workflow-runs?page=${page}&limit=${limit}`)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [page])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Runs</h1>
      <State loading={loading} error={error}>
        {data && (
          <>
            <div className="rounded-xl border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="px-4 py-2">ID</th>
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Workflow</th>
                    <th className="px-4 py-2">Org</th>
                    <th className="px-4 py-2">Mode</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data.workflow_runs.map((r) => (
                    <tr key={r.id} className="border-b border-gray-100">
                      <td className="px-4 py-2 text-gray-600">{r.id}</td>
                      <td className="px-4 py-2 font-medium text-gray-900">{r.name || '-'}</td>
                      <td className="px-4 py-2 text-gray-600">{r.workflow_name || r.workflow_id}</td>
                      <td className="px-4 py-2 text-gray-600">{r.organization_name || r.organization_id || '-'}</td>
                      <td className="px-4 py-2 text-gray-600">{r.mode}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            r.is_completed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                          }`}
                        >
                          {r.is_completed ? 'Completed' : 'Active'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{fmtDate(r.created_at)}</td>
                    </tr>
                  ))}
                  {data.workflow_runs.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-gray-500">
                        No runs found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <Pager page={page} totalPages={data.total_pages} onChange={setPage} />
          </>
        )}
      </State>
    </div>
  )
}