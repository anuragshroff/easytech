import React, { useEffect, useState } from 'react'
import { api } from './api.js'

export default function Pager({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between pt-4">
      <button
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-40"
      >
        Prev
      </button>
      <span className="text-sm text-gray-600">
        Page {page} of {totalPages}
      </span>
      <button
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
        className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-40"
      >
        Next
      </button>
    </div>
  )
}

export function State({ loading, error, children }) {
  if (loading) return <p className="text-gray-500">Loading...</p>
  if (error) return <p className="text-red-500">{error}</p>
  return children
}

export function fmtDate(value) {
  if (!value) return '-'
  const d = new Date(value)
  return isNaN(d) ? '-' : d.toLocaleString()
}

export function SearchBox({ value, onChange, placeholder }) {
  return (
    <input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder || 'Search...'}
      className="w-64 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
    />
  )
}