const API_BASE = '/api/v1'

export function getToken() {
  return localStorage.getItem('admin_token')
}

export function setSession(token, user) {
  localStorage.setItem('admin_token', token)
  localStorage.setItem('admin_user', JSON.stringify(user))
}

export function getSessionUser() {
  try {
    return JSON.parse(localStorage.getItem('admin_user') || 'null')
  } catch {
    return null
  }
}

export function logout() {
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_user')
  window.location.href = '/superadmin/login'
}

export async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const t = getToken()
  if (t) headers['Authorization'] = `Bearer ${t}`
  const res = await fetch(API_BASE + path, { ...options, headers })
  if (res.status === 401) {
    logout()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    let msg = `Request failed: ${res.status}`
    try {
      const data = await res.json()
      msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data)
    } catch {
      /* keep default message */
    }
    throw new Error(msg)
  }
  return res.json()
}