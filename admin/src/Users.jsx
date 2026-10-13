import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import Pager, { SearchBox, State, fmtDate } from './Shared.jsx'

export default function Users() {
  const [page, setPage] = useState(1)
  const [limit] = useState(50)
  const [search, setSearch] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api(`/superuser/users?page=${page}&limit=${limit}&search=${encodeURIComponent(search || '')}`)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [page, search])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search by email..." />
      </div>
      <State loading={loading} error={error}>
        {data && (
          <>
            <div className="rounded-xl border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="px-4 py-2">ID</th>
                    <th className="px-4 py-2">Email</th>
                    <th className="px-4 py-2">Provider</th>
                    <th className="px-4 py-2">Role</th>
                    <th className="px-4 py-2">Org ID</th>
                    <th className="px-4 py-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data.users.map((u) => (
                    <tr key={u.id} className="border-b border-gray-100">
                      <td className="px-4 py-2 text-gray-600">{u.id}</td>
                      <td className="px-4 py-2 font-medium text-gray-900">{u.email || '-'}</td>
                      <td className="px-4 py-2 text-gray-600">{u.provider_id}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            u.is_superuser ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          {u.is_superuser ? 'Admin' : 'User'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{u.organization_id ?? '-'}</td>
                      <td className="px-4 py-2 text-gray-600">{fmtDate(u.created_at)}</td>
                    </tr>
                  ))}
                  {data.users.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-gray-500">
                        No users found
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