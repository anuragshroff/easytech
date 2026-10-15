import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { State } from './Shared.jsx'

const DEFAULTS = {
  rate_cents_per_minute: 10,
  minimum_balance_cents: 100,
  enforce_pre_call_balance: false,
  auto_recharge_threshold_cents: 500,
  auto_recharge_amount_cents: 2000,
}

export default function Billing() {
  const [data, setData] = useState(null)
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState('')

  useEffect(() => {
    api('/superuser/billing/settings')
      .then((d) => {
        setData(d)
        setLinks(d.payment_links || [])
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  function setField(key, value) {
    setData((d) => ({ ...d, [key]: value }))
    setSaved('')
  }

  function setLink(i, key, value) {
    setLinks((ls) => ls.map((l, idx) => (idx === i ? { ...l, [key]: value } : l)))
    setSaved('')
  }

  async function save() {
    setSaving(true)
    setSaved('')
    try {
      const payload = {
        ...DEFAULTS,
        ...data,
        payment_links: links
          .filter((l) => l.url)
          .map((l) => ({
            label: l.label || '',
            amount_cents: Number(l.amount_cents) || 0,
            url: l.url,
          })),
      }
      const updated = await api('/superuser/billing/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setData(updated)
      setLinks(updated.payment_links || [])
      setSaved('Saved')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const num = (key, label) => (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-gray-700">{label}</span>
      <input
        type="number"
        className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        value={data?.[key] ?? ''}
        onChange={(e) => setField(key, Number(e.target.value))}
      />
    </label>
  )

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
      <div className="text-sm text-gray-600">
        Platform wallet pricing and Stripe Payment Links. Per-org overrides override these; unset fields inherit here.
      </div>
      <State loading={loading} error={error}>
        {data && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 rounded-xl border border-gray-200 bg-white p-4">
              {num('rate_cents_per_minute', 'Rate (cents / minute)')}
              {num('minimum_balance_cents', 'Minimum balance (cents)')}
              {num('auto_recharge_threshold_cents', 'Auto-recharge threshold (cents)')}
              {num('auto_recharge_amount_cents', 'Auto-recharge amount (cents)')}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={!!data.enforce_pre_call_balance}
                  onChange={(e) => setField('enforce_pre_call_balance', e.target.checked)}
                />
                <span className="font-medium text-gray-700">
                  Enforce pre-call balance (block calls when under minimum)
                </span>
              </label>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="font-medium text-gray-900">Stripe Payment Links</div>
                <button
                  className="rounded-lg bg-gray-900 px-3 py-1.5 text-sm font-medium text-white"
                  onClick={() => setLinks((ls) => [...ls, { label: '', amount_cents: 0, url: '' }])}
                >
                  Add link
                </button>
              </div>
              <div className="text-xs text-gray-500 mb-2">
                Append <code>?client_reference_id=&lt;org_id&gt;</code> to each link so completed checkouts credit the right org.
              </div>
              <div className="space-y-2">
                {links.map((l, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      className="w-40 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="Label"
                      value={l.label || ''}
                      onChange={(e) => setLink(i, 'label', e.target.value)}
                    />
                    <input
                      type="number"
                      className="w-32 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="Amount (cents)"
                      value={l.amount_cents ?? ''}
                      onChange={(e) => setLink(i, 'amount_cents', Number(e.target.value))}
                    />
                    <input
                      className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="https://buy.stripe.com/..."
                      value={l.url || ''}
                      onChange={(e) => setLink(i, 'url', e.target.value)}
                    />
                    <button
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
                      onClick={() => setLinks((ls) => ls.filter((_, idx) => idx !== i))}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {links.length === 0 && (
                  <div className="text-sm text-gray-500">No payment links configured.</div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                disabled={saving}
                onClick={save}
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
              {saved && <span className="text-sm text-green-600">{saved}</span>}
            </div>
          </div>
        )}
      </State>
    </div>
  )
}
