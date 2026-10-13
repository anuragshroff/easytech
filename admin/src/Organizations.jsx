import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import Pager, { SearchBox, State, fmtDate } from './Shared.jsx'

export default function Organizations() {
  const [page, setPage] = useState(1)
  const [limit] = useState(50)
  const [search, setSearch] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api(
      `/superuser/organizations?page=${page}&limit=${limit}&search=${encodeURIComponent(search || '')}`
    )
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [page, search])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Organizations</h1>
        <SearchBox
          value={search}
          onChange={(v) => { setSearch(v); setPage(1) }}
          placeholder="Search by provider ID..."
        />
      </div>
      <State loading={loading} error={error}>
        {data && (
          <>
            <div className="rounded-xl border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="px-4 py-2">ID</th>
                    <th className="px-4 py-2">Provider</th>
                    <th className="px-4 py-2">Users</th>
                    <th className="px-4 py-2">Runs</th>
                    <th className="px-4 py-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data.organizations.map((o) => (
                    <tr key={o.id} className="border-b border-gray-100">
                      <td className="px-4 py-2 text-gray-600">{o.id}</td>
                      <td className="px-4 py-2 font-medium text-gray-900">{o.provider_id}</td>
                      <td className="px-4 py-2 text-gray-600">{o.user_count}</td>
                      <td className="px-4 py-2 text-gray-600">{o.run_count}</td>
                      <td className="px-4 py-2 text-gray-600">{fmtDate(o.created_at)}</td>
                    </tr>
                  ))}
                  {data.organizations.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-gray-500">
                        No organizations found
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