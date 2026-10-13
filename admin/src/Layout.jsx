import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { getSessionUser, logout } from './api.js'

const links = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/users', label: 'Users' },
  { to: '/organizations', label: 'Organizations' },
  { to: '/runs', label: 'Runs' },
]

export default function Layout() {
  const user = getSessionUser()
  return (
    <div className="flex min-h-screen bg-gray-100">
      <aside className="flex w-56 flex-col bg-gray-950">
        <div className="px-5 py-5">
          <div className="text-lg font-bold text-white">Dograh Admin</div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-800 p-3">
          <div className="truncate px-1 text-sm text-gray-300">{user?.email || 'Unknown'}</div>
          <button
            onClick={logout}
            className="mt-2 w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}