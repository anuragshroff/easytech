import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from './api.js'
import Pager, { State, fmtDate } from './Shared.jsx'

export default function OrganizationDetail() {
  const { orgId } = useParams()
  const [detail, setDetail] = useState(null)
  const [members, setMembers] = useState([])
  const [workflows, setWorkflows] = useState([])
  const [runs, setRuns] = useState({ runs: [], total_count: 0, total_pages: 1, page: 1 })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      api(`/superuser/organizations/${orgId}`),
      api(`/superuser/organizations/${orgId}/members`),
      api(`/superuser/organizations/${orgId}/workflows`),
      api(`/superuser/organizations/${orgId}/runs?page=${page}&limit=25`),
    ])
      .then(([d, m, w, r]) => {
        setDetail(d)
        setMembers(m.users || [])
        setWorkflows(w.workflows || [])
        setRuns(r)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [orgId, page])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Organization {orgId}</h1>
        <Link to="/organizations" className="text-sm text-indigo-600 hover:underline">Back to organizations</Link>
      </div>
      <State loading={loading} error={error}>
        {detail && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            <Kpi label="Provider" value={detail.provider_id} />
            <Kpi label="Users" value={detail.user_count} />
            <Kpi label="Workflows" value={detail.workflow_count} />
            <Kpi label="Runs" value={detail.run_count} />
            <Kpi label="Price/s" value={detail.price_per_second_usd ?? '-'} />
            <Kpi label="Created" value={fmtDate(detail.created_at)} />
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-medium text-gray-900">Members</h2>
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-2">ID</th>
                  <th className="pb-2">Email</th>
                  <th className="pb-2">Role</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {members.map((u) => (
                  <tr key={u.id} className="border-b border-gray-100">
                    <td className="py-2 text-gray-600">{u.id}</td>
                    <td className="py-2 text-gray-900">{u.email || '-'}</td>
                    <td className="py-2 text-gray-600">{u.is_superuser ? 'Admin' : 'User'}</td>
                    <td className="py-2 text-gray-600">{(u.is_active ?? true) ? 'Active' : 'Disabled'}</td>
                  </tr>
                ))}
                {members.length === 0 && (
                  <tr><td colSpan={4} className="py-4 text-center text-gray-500">No members</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-medium text-gray-900">Workflows</h2>
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-2">ID</th>
                  <th className="pb-2">Name</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Runs</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((w) => (
                  <tr key={w.id} className="border-b border-gray-100">
                    <td className="py-2 text-gray-600">{w.id}</td>
                    <td className="py-2 text-gray-900">{w.name || '-'}</td>
                    <td className="py-2 text-gray-600">{w.status || '-'}</td>
                    <td className="py-2 text-gray-600">{w.run_count}</td>
                    <td className="py-2 text-gray-600">{fmtDate(w.created_at)}</td>
                  </tr>
                ))}
                {workflows.length === 0 && (
                  <tr><td colSpan={5} className="py-4 text-center text-gray-500">No workflows</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="text-lg font-medium text-gray-900">Runs</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500">
                <th className="pb-2">ID</th>
                <th className="pb-2">Name</th>
                <th className="pb-2">Workflow</th>
                <th className="pb-2">Mode</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {(runs.runs || []).map((r) => (
                <tr key={r.id} className="border-b border-gray-100">
                  <td className="py-2 text-gray-600">{r.id}</td>
                  <td className="py-2 text-gray-900">{r.name || `Run ${r.id}`}</td>
                  <td className="py-2 text-gray-600">{r.workflow_id} {r.workflow_name ? `(${r.workflow_name})` : ''}</td>
                  <td className="py-2 text-gray-600">{r.mode}</td>
                  <td className="py-2">{r.is_completed ? 'Completed' : 'Active'}</td>
                  <td className="py-2 text-gray-600">{fmtDate(r.created_at)}</td>
                </tr>
              ))}
              {runs.runs && runs.runs.length === 0 && (
                <tr><td colSpan={6} className="py-4 text-center text-gray-500">No runs</td></tr>
              )}
            </tbody>
          </table>
          <Pager page={page} totalPages={runs.total_pages || 1} onChange={setPage} />
        </div>
      </State>
    </div>
  )
}

function Kpi({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-gray-900 truncate">{value}</div>
    </div>
  )
}
