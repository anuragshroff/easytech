import React, { useEffect, useState } from 'react'
import { api, getSessionUser } from './api.js'
import Pager, { SearchBox, State, fmtDate } from './Shared.jsx'

export default function Users() {
  const [page, setPage] = useState(1)
  const [limit] = useState(50)
  const [search, setSearch] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actingId, setActingId] = useState(null)

  async function toggleSuperuser(u) {
    const next = !u.is_superuser
    if (!confirm(`${next ? 'Promote' : 'Demote'} ${u.email || u.id} to ${next ? 'superadmin' : 'user'}?`)) return
    setActingId(u.id)
    try {
      await api(`/superuser/users/${u.id}/superuser`, { method: 'POST', body: JSON.stringify({ is_superuser: next }) })
      setData((prev) => prev ? { ...prev, users: prev.users.map(x => x.id === u.id ? { ...x, is_superuser: next } : x) } : prev)
    } catch (err) {
      alert(err.message)
    } finally {
      setActingId(null)
    }
  }

  async function toggleActive(u) {
    const next = !(u.is_active ?? true)
    if (!confirm(`${next ? 'Disable' : 'Enable'} ${u.email || u.id}?`)) return
    setActingId(u.id)
    try {
      await api(`/superuser/users/${u.id}/active`, { method: 'POST', body: JSON.stringify({ is_active: next }) })
      setData((prev) => prev ? { ...prev, users: prev.users.map(x => x.id === u.id ? { ...x, is_active: next } : x) } : prev)
    } catch (err) {
      alert(err.message)
    } finally {
      setActingId(null)
    }
  }

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
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Org ID</th>
                    <th className="px-4 py-2">Created</th>
                    <th className="px-4 py-2">Actions</th>
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
                      <td className="px-4 py-2">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            (u.is_active ?? true) ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'
                          }`}
                        >
                          {(u.is_active ?? true) ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{u.organization_id ?? '-'}</td>
                      <td className="px-4 py-2 text-gray-600">{fmtDate(u.created_at)}</td>
                      <td className="px-4 py-2 space-x-1">
                        <button
                          onClick={() => toggleSuperuser(u)}
                          disabled={actingId === u.id || u.id === meId}
                          className="rounded-md border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-50 disabled:opacity-40"
                        >
                          {actingId === u.id ? 'Saving...' : (u.is_superuser ? 'Demote' : 'Promote')}
                        </button>
                        <button
                          onClick={() => toggleActive(u)}
                          disabled={actingId === u.id || u.id === meId}
                          className="rounded-md border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-50 disabled:opacity-40"
                        >
                          {actingId === u.id ? 'Saving...' : ((u.is_active ?? true) ? 'Disable' : 'Enable')}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {data.users.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-6 text-center text-gray-500">
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